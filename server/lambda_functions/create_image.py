# 
#  Given an image, this Lambda function uploads the image to the
#  database and to S3. 
#

import boto3
import json
import uuid
import os
import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential

s3 = boto3.client('s3')
sqs = boto3.client("sqs")

BUCKET = os.environ["BUCKET_NAME"]
QUEUE_URL = os.environ["SQS_QUEUE_URL"]

#
# helper for opening DB connection, retrieve from lambda function env variables 
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

# helper for insertion into SQL table
@retry (
    stop = stop_after_attempt(3),
    wait = wait_exponential(multiplier=1, min=2, max=10),
    reraise = True      
)
def insert_image(image_id, s3_key):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()
        dbConn.begin()

        sql = """
        INSERT INTO images (image_id, s3_key)
        VALUES (%s, %s);
        """

        dbCursor.execute(sql, [image_id, s3_key])
        if dbCursor.rowcount != 1:
            raise RuntimeError("failed to insert image")

        dbConn.commit()
    except Exception as error:
        dbConn.rollback()
        raise error
    finally:
        try:
            dbConn.close()
        except:
            pass



def lambda_handler(event, context):
    try:
        # generate ID for the image 
        image_bytes = event['body']
        image_id = str(uuid.uuid4())
        s3_key = "images/" + image_id + ".jpg"

        # upload image to the S3 bucket
        s3.put_object(
            Bucket = BUCKET,
            Key = s3_key, 
            Body = image_bytes,
            ContentType="image/jpeg" # only works w/ jpg images 
        )

        # call helper function for insertion into SQL table
        insert_image(image_id, s3_key)

        # send message to SQS queue
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps({
                "image_id": image_id
            })
        )

        # return the image ID upon success
        return {
            "statusCode": 200,
            "body": json.dumps({"image_id": image_id})
        }

    # handle failures 
    except Exception as err:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "error in creating image"})
        }