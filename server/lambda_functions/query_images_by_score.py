import psycopg2
import json
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential


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
# helper to query images by score
#
def query_images(score_type, threshold, dbCursor):
    column = ""
    if score_type == "harmony":
        column = "harmony_score"
    elif score_type == "contrast":
        column = "contrast_score"
    else:
        raise ValueError("invalid score_type (must be harmony or contrast)")

    # ok since it's not user input 
    sql = """
        SELECT image_id, {column} 
        FROM images
        WHERE {column} IS NOT NULL
        AND {column} >= %s
        ORDER BY {column} DESC;
        """

    dbCursor.execute(sql, [threshold])
    rows = dbCursor.fetchall()

    results = []
    for row in rows:

        results.append({
            "image_id": row[0],
            column: row[1]
        })

    return results


#
# main logic
#
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def query_images_by_score(score_type, threshold):
    try:
        dbConn = get_dbConn()
        dbCursor = dbConn.cursor()

        results = query_images(score_type, threshold, dbCursor)

        return results
    except Exception as err:
        logging.error("error in query_images_by_score")
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
        score_type = event["score_type"]
        threshold = float(event["threshold"])

        results = query_images_by_score(score_type, threshold)

        return {
            "statusCode": 200,
            "body": json.dumps(results)
        }

    except ValueError as err:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(err)})
        }
    except Exception:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "erroring in querying images by score"})
        }