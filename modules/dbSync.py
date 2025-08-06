import os
import re
import logging
import mysql.connector
from datetime import datetime, date
from modules.runTimeSecrets import HOST, DB, USER, PASS

# ------------------------------ LOGGER ------------------------------
import logging
def loggerInit(logFileName):
    try: os.makedirs("logs")
    except: pass
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
    file_handler = logging.FileHandler(f'logs/{logFileName}')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
logger = loggerInit(logFileName="db.sync.log")
# ------------------------------ LOGGER ------------------------------

def processQueries(data):
    updateGcode(10021, data['DATA']['Product ID'], data['GCODE'], data['DATA']['DB Product URL'], data['DATA']['Scrapped Product URL'])

def updateMYSQL(scrapedData):
    processQueries(scrapedData)
    logger.debug("Completed Run")

# Updating product gcode
def updateGcode(vendor_id, product_id, gcode, db_product_url, scrapped_product_url):
    try:
        conn = mysql.connector.connect(host=HOST, database=DB, user=USER, password=PASS)
        if conn.is_connected():
            this = conn.cursor()
            if db_product_url in scrapped_product_url:
                this.execute("UPDATE Product SET gcode = %s WHERE product_id = %s AND gcode IS NULL;", (gcode, product_id))
                conn.commit()
                if this.rowcount == 1:
                    logger.info(f'Updated gcode for product_id ({product_id}).')
                    currentDayScraped(product_id, gcode)
                else:
                    this.execute("SELECT gcode FROM Product WHERE product_id = %s LIMIT 1;", (product_id,))
                    result = this.fetchone()
                    if result:
                        gcodeDB = result[0]
                        if gcodeDB != gcode:
                            this.execute("""
                                SELECT
                                    product_secondary_gcode_id
                                FROM ProductSecondaryGcode
                                WHERE
                                    product_id = %s
                                    AND secondary_gcode = %s;
                            """, (product_id, gcode))
                            records = this.fetchall()
                            if len(records) == 0:
                                this.execute("INSERT INTO ProductSecondaryGcode (product_id, secondary_gcode) VALUES (%s, %s);", (product_id, gcode))
                                conn.commit()
                                if this.rowcount == 1:
                                    logger.info(f'Added a new secondary gcode for product_id ({this.lastrowid}).')
            else:
                scrapped_product_url = scrapped_product_url.split('?')[0].strip()
                # ----------------------------------------------------------------------------------------------------------------------------------------

                this.execute("""
                    SELECT
                        ProductVendor.product_id
                    FROM ProductVendor
                    INNER JOIN VendorURL ON VendorURL.vendor_product_id = ProductVendor.vendor_product_id
                    WHERE
                        ProductVendor.vendor_id = %s
                        AND VendorURL.vendor_url = %s
                    LIMIT 1;
                """, (vendor_id, scrapped_product_url))
                records2 = this.fetchone()
                if records2:
                    other_product_id = records2[0]
                    this.execute("UPDATE Product SET gcode = %s WHERE product_id = %s AND gcode IS NULL;", (gcode, other_product_id))
                    conn.commit()
                    if this.rowcount == 1:
                        logger.info(f'Updated gcode for other product_id ({other_product_id}).')
                    else:
                        this.execute("SELECT gcode FROM Product WHERE product_id = %s LIMIT 1;", (other_product_id,))
                        result2 = this.fetchone()
                        if result2:
                            gcodeDB = result2[0]
                            if gcodeDB != gcode:
                                this.execute("""
                                    SELECT
                                        product_secondary_gcode_id
                                    FROM ProductSecondaryGcode
                                    WHERE
                                        product_id = %s
                                        AND secondary_gcode = %s;
                                """, (other_product_id, gcode))
                                records3 = this.fetchall()
                                if len(records3) == 0:
                                    this.execute("INSERT INTO ProductSecondaryGcode (product_id, secondary_gcode) VALUES (%s, %s);", (other_product_id, gcode))
                                    conn.commit()
                                    if this.rowcount == 1:
                                        logger.info(f'Added a new secondary gcode for product_id ({this.lastrowid}).')
    except mysql.connector.Error as e:
        print(f"updateGcode() >> {e}")
    finally:
        if conn.is_connected():
            this.close()
            conn.close()

def currentDayScraped(product_id, gcode):
    """
    Saving today's scraped products
    """
    processedCountFile = f"/root/public/GcodeFinderBrandMpn(AF)/({date.today()})scraped"
    if os.path.exists(processedCountFile):
        with open(processedCountFile, "a") as f:
            f.write(str(product_id) + " " + str(gcode) + "\n")
    else:
        with open(processedCountFile, "w") as f:
            f.write(str(product_id) + " " + str(gcode) + "\n")