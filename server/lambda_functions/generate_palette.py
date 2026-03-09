# 
#  Given an image, this Lambda function uploads the image to the
#  database and to S3. 
#

import boto3
import json
import uuid
import os
import pymysql
from tenacity import retry, stop_after_attempt, wait_exponential
import numpy as np 
from PIL import Image
from sklearn.cluster import KMeans
from io import BytesIO

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET_NAME"]

#
# helper for opening DB connection, retrieve from lambda function env variables 
#
def get_dbConn():
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        autocommit=False
    )

    return conn

#
# retrieve the S3 key from DB
#
@retry (
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True      
)
def get_s3(image_id):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        # sql to get the s3 key
        sql = """
        SELECT s3_key FROM images WHERE image_id = %s;
        """

        dbCursor.execute(sql, [image_id])
        row = dbCursor.fetchone()
        
        if not row:
            raise ValueError("image not found")

        return row[0]
    except Exception as err:
        raise
    finally: 
        try:
            dbConn.close()
        except:
            pass

#
# downloads the image from s3, given the s3 bucket key
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
# extract the palette from the image using numpy and k-means
#
def extract_palette(image):
    image = image.resize((100, 100))

    pixels = np.array(image)
    pixels = pixels.reshape(-1, 3)

    # use kmeans to generate a color palette 
    kmeans = KMeans(n_clusters = 5)
    kmeans.fit(pixels)

    colors = kmeans.cluster_centers_
    palette = [list(map(int, c)) for c in colors]

    return palette

#
# store the palette in the DB, uses retry 
#
@retry (
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True      
)
def store_palette(image_id, palette):
    try: 
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        # begin transaction
        dbConn.begin()

        sql = """
        UPDATE images
        SET palette = %s
        WHERE image_id = %s;
        """

        dbCursor.execute(sql, [json.dumps(palette), image_id])

        dbConn.commit()
    except Exception as err:
        dbConn.rollback()
        raise
    finally:
        try:
            dbConn.close()
        except:
            pass

def lambda_handler(event, context):
    try:
        # grab the image id from the event
        image_id = event['image_id']

        s3_key = get_s3(image_id)
        image = download_image(s3_key)
        palette = extract_palette(image)

        # store the palette in the DB 
        store_palette(image_id, palette)

        return {
            "statusCode": 200,
            "body": json.dumps({"palette": palette})
        }

    except Exception as err:
        return {
            "statusCode": 500,
            "body": str(err)
        }