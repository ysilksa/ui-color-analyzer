import psycopg2
import json
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential


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

#
# convert RGB palette to hex colors for UI display
#
def rgb_to_hex(palette):

    hex_colors = []

    for r, g, b in palette:
        hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)
        hex_colors.append(hex_color)

    return hex_colors


#
# retrieve image info
#
def get_image_data(image_id, dbCursor):

    sql = """
    SELECT palette, harmony_score, contrast_score
    FROM images
    WHERE image_id = %s;
    """

    dbCursor.execute(sql, [image_id])
    row = dbCursor.fetchone()

    if not row:
        raise ValueError("no such image ID")

    return row


#
# main logic
#
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def get_image_details(image_id):

    dbConn = None
    dbCursor = None

    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        row = get_image_data(image_id, dbCursor)

        result = {"image_id": image_id}

        palette = row[0]
        harmony_score = row[1]
        contrast_score = row[2]

        # add palette if exists
        if palette is not None:
            result["palette"] = rgb_to_hex(palette)

        # add harmony score if exists
        if harmony_score is not None:
            result["harmony_score"] = harmony_score

        # add contrast score if computed
        if contrast_score is not None:
            result["contrast_score"] = contrast_score

        return result

    except Exception as err:
        logging.error("error in get_image_details")
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
# lambda handler
#
def lambda_handler(event, context):
    try:
        logging.info(json.dumps(event))
        image_id = None

        if event.get("pathParameters"):
            image_id = event["pathParameters"].get("imageId")

        if not image_id:
            raise ValueError("missing image_id")
        result = get_image_details(image_id)

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
    except ValueError as err:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(err)})
        }
    except Exception:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "server error in retrieving image details"})
        }