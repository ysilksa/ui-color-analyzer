# 
#  Given an image, this Lambda function uploads the image to the
#  database and to S3. 
#

import boto3
import uuid
from tenacity import retry, stop_after_attempt, wait_exponential

s3 = boto3.client('s3')
BUCKET = ""

def lambda_handler(event, context):
    # generate ID for the image 

    # upload image to the S3 bucket

    # call helper function for insertion into SQL table

    # return the image ID upon success

    # handle failures 