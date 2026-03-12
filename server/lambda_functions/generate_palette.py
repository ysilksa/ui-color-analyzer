import boto3
import json
import os
import psycopg2
import logging
import numpy as np
from PIL import Image
from io import BytesIO
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)

s3 = boto3.client("s3")
sqs = boto3.client("sqs")

BUCKET = os.environ["BUCKET_NAME"]
QUEUE_URL = os.environ["QUEUE_URL"]


#
# helper for opening DB connection
#
def get_dbConn():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        port=5432
    )

    conn.autocommit = False
    return conn


#
# retrieve the S3 key from DB
#
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def get_s3(image_id):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        sql = """
        SELECT s3_key FROM images WHERE image_id = %s;
        """

        dbCursor.execute(sql, [image_id])
        row = dbCursor.fetchone()

        if not row:
            raise ValueError("image not found")

        return row[0]

    finally:
        try:
            dbConn.close()
        except:
            pass


#
# download image from S3
#
def download_image(s3_key):
    response = s3.get_object(
        Bucket=BUCKET,
        Key=s3_key
    )

    image_bytes = response["Body"].read()
    image = Image.open(BytesIO(image_bytes))

    return image


#
# extract palette with simple k-means
#
def extract_palette(image, k=5, max_iters=10):
    image = image.resize((100, 100))

    pixels = np.array(image)
    pixels = pixels.reshape(-1, 3)
    rng = np.random.default_rng()
    centers = pixels[rng.choice(len(pixels), k, replace=False)]

    for _ in range(max_iters):
        distances = np.linalg.norm(pixels[:, None] - centers, axis=2)
        labels = np.argmin(distances, axis=1)
        new_centers = np.array([
            pixels[labels == i].mean(axis=0) if np.any(labels == i) else centers[i]
            for i in range(k)
        ])
        if np.allclose(centers, new_centers):
            break
        centers = new_centers

    palette = centers.astype(int).tolist()

    return palette


#
# store palette in DB
#
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def store_palette(image_id, palette):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        sql = """
        UPDATE images
        SET palette = %s
        WHERE image_id = %s;
        """

        dbCursor.execute(sql, [json.dumps(palette), image_id])

        dbConn.commit()

    except Exception:
        dbConn.rollback()
        raise

    finally:
        try:
            dbConn.close()
        except:
            pass


#
# Lambda entry point
#
def lambda_handler(event, context):
    try:
        logging.info("EVENT:")
        logging.info(json.dumps(event))
        for record in event["Records"]:
            body = json.loads(record["body"])
            image_id = body["image_id"]

            logging.info(f"Generating palette for {image_id}")

            s3_key = get_s3(image_id)
            image = download_image(s3_key)
            palette = extract_palette(image)
            store_palette(image_id, palette)

            # send message to next queue
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({
                    "image_id": image_id
                })
            )
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "palette generated"})
        }
    except Exception as err:
        logging.error(str(err))

        return {
            "statusCode": 500,
            "body": json.dumps({"error": "error generating palette"})
        }