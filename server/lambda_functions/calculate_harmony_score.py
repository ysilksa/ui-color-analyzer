#
# Given an image ID, the image will be retrieved, and its harmony score will be calculated from the palette given. 
# If the image has no palette yet, a client error is returned and the user is told to generate the palette first. 
#

import os
import psycopg2
import json
import colorsys
import logging
import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)

sqs = boto3.client("sqs")
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
# helper for retrieving palette based on image ID
#
def get_palette(image_id, dbCursor):
    sql = """
    SELECT palette FROM images WHERE image_id = %s;
    """
    dbCursor.execute(sql, [image_id])
    row = dbCursor.fetchone()

    if not row:
        raise ValueError("no such image ID")
    if row[0] is None:
        raise ValueError("please generate the palette for this image first!")

    return row[0]


#
# helper for turning RGB colors to HSB
#
def rgb_to_hues(palette):
    hues = []

    for r, g, b in palette:
        r /= 255
        g /= 255
        b /= 255
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        hues.append(h * 360)

    return hues


#
# helper to calculate distance between two hues
#
def calculate_hue_distance(h1, h2):
    diff = abs(h1 - h2)
    return min(diff, 360 - diff)

#
# helper to compute harmony score
#
def compute_harmony(hues):
    score = 0
    comparisons = 0
    hues_len = len(hues)

    for i in range(hues_len):
        for j in range(i + 1, hues_len):
            distance = calculate_hue_distance(hues[i], hues[j])
            comparisons += 1

            # complementary
            if 150 <= distance <= 210:
                score += 1

            # analogous
            elif distance <= 30:
                score += 0.5

            # triadic
            elif 100 <= distance <= 140:
                score += 0.8

    if comparisons > 0:
        score = score / comparisons

    return score

#
# store the harmony score
#
def store_harmony_score(image_id, score, dbCursor):
    sql = """
    UPDATE images
    SET harmony_score = %s
    WHERE image_id = %s;
    """

    dbCursor.execute(sql, [score, image_id])


#
# main logic for creating harmony score
#
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def create_harmony_score(image_id):
    dbConn = None
    dbCursor = None

    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        palette = get_palette(image_id, dbCursor)
        hues = rgb_to_hues(palette)
        score = compute_harmony(hues)
        store_harmony_score(image_id, score, dbCursor)

        dbConn.commit()

        return score
    except Exception as err:
        if dbConn:
            dbConn.rollback()

        logging.error("error in create_harmony_score")
        logging.error(str(err))

        raise
    finally:
        try:
            if dbCursor:
                dbCursor.close()
        except:
            pass

        try:
            if dbConn:
                dbConn.close()
        except:
            pass


#
# lambda handler sqs 
#
def lambda_handler(event, context):

    try:
        for record in event["Records"]:
            body = json.loads(record["body"])
            image_id = body["image_id"]
            logging.info(f"Calculating harmony score for {image_id}")
            score = create_harmony_score(image_id)

            # send message to next queue
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({
                    "image_id": image_id
                })
            )
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "harmony score calculated"})
        }
    except ValueError as err:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(err)})
        }

    except Exception as err:
        logging.error(str(err))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "error creating harmony score"})
        }