# 
#  Given an image, this Lambda function uploads the image to the
#  database and to S3. 
#

import boto3
import json
import uuid
from tenacity import retry, stop_after_attempt, wait_exponential

s3 = boto3.client('s3')
BUCKET = ""

def lambda_handler(event, context):
    try:
        # generate ID for the image 
        image_bytes = event['body']
        image_id = str(uuid.uuid4())
        s3_key = "images/" + image_id + ".jpg"

        # upload image to the S3 bucket
        s3.put_object(
            bucket = BUCKET,
            Key = s3_key, 
            Body = image_bytes
        )

        # call helper function for insertion into SQL table

        # return the image ID upon success
        return {
            "statusCode": 200,
            "body": json.dumps({"image_id": image_id})
        }

    # handle failures 
    except Exception as err:
        pass