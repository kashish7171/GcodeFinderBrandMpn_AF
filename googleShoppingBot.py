import os
import time
import psutil
import logging
from datetime import date
import multiprocessing
import mysql.connector
from modules.googleScrapper import core as scrapperCore
from modules.runTimeSecrets import HOST, DB, USER, PASS

# ----------------------------- LOGGER ------------------------------
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
logger = loggerInit(logFileName="google.shopping.log")
# ----------------------------- LOGGER ------------------------------

def getKeywordFromDB():
    try:
        conn = mysql.connector.connect(host=HOST, database=DB, user=USER, password=PASS)
        if conn.is_connected():
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    Brand.brand_name,
                    Product.product_mpn,
                    Product.product_id,
                    VendorURL.vendor_url
                FROM Product
                INNER JOIN Brand ON Brand.brand_id = Product.brand_id
                INNER JOIN ProductVendor ON ProductVendor.product_id = Product.product_id
                INNER JOIN VendorURL ON VendorURL.vendor_product_id = ProductVendor.vendor_product_id
                WHERE
                    ProductVendor.vendor_id = %s
                    AND Product.gcode IS NULL
                    AND Product.is_picked = '0'
                    AND Product.product_mpn NOT LIKE 'Temp%'
                    AND Brand.brand_id NOT IN (1201)
                    AND Brand.brand_name NOT IN ("DaVinci")
                GROUP BY Product.product_id
                ORDER BY Product.created_at DESC
                LIMIT 1;
            """, (10021,))
            result = cursor.fetchall()
            pickedKeyword = []
            keyword, productIDs, productURLs = {}, {}, {}
            if len(result) > 0:
                for row in result:
                    keyword[f'{row[0]} {row[1]}'] = '2'
                    productIDs[f'{row[0]} {row[1]}'] = row[2]
                    productURLs[f'{row[0]} {row[1]}'] = row[3]

                    pickedKeyword.append(f'{row[2]}')
                # # Setting product IDs as picked
                # product_ids_to_update = ','.join(pickedKeyword)
                # cursor.execute(f"UPDATE Product SET is_picked = '1' WHERE product_id IN ({product_ids_to_update})")
                # conn.commit()
                # currentDayProcessed(product_ids_to_update)
                # if cursor.rowcount == 1: logger.debug(f'Keywords set to picked')
                return [keyword, productIDs, productURLs]
            # else:
            #     cursor.execute("""
            #         UPDATE Product
            #         SET is_picked = '0'
            #         WHERE
            #             product_id IN (
            #                 SELECT
            #                     DISTINCT Product.product_id
            #                 FROM Product
            #                 INNER JOIN Brand ON Brand.brand_id = Product.brand_id
            #                 INNER JOIN ProductVendor ON ProductVendor.product_id = Product.product_id
            #                 INNER JOIN VendorURL ON VendorURL.vendor_product_id = ProductVendor.vendor_product_id
            #                 WHERE
            #                     ProductVendor.vendor_id = %s
            #                     AND Product.gcode IS NULL
            #                     AND Product.product_mpn NOT LIKE 'Temp%'
            #                     AND Brand.brand_id NOT IN (1201)
            #                 ORDER BY Product.created_at DESC
            #             );
            #     """, (10021,))
            #     conn.commit()
            #     getKeywordFromDB()
            return []
    except mysql.connector.Error as e:
        print(f"MySQL ERROR getKeywordFromDB() >> {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# to monitor system resources and pause/resume processes based on CPU and memory usage
def monitor_resources(processes, pause_events, max_runtime=300):
    paused_process = None
    # Track start time for each process
    start_times = {p: time.time() for p in processes}

    while any(p.is_alive() for p in processes):
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)

        print(f"Paused process: ({paused_process}).")
        print(f"Memory usage ({memory_usage}%) x CPU usage ({cpu_usage}%).")
        if memory_usage > 80 or cpu_usage > 90:
            logging.warning(f"Memory usage ({memory_usage}%) or CPU usage ({cpu_usage}%) too high.")
            
            # Pause one process to free up memory (pause the first process)
            if paused_process is None:
                for i, p in enumerate(processes):
                    if p.is_alive():
                        paused_process = p
                        pause_events[i].clear()  # Clear event to pause the process
                        logging.info(f"Pausing process {p.name}")
                        break
            time.sleep(10)  # Wait and check again
        else:
            if paused_process is not None:
                paused_process_index = processes.index(paused_process)
                pause_events[paused_process_index].set()  # Set event to resume the paused process
                logging.info(f"Resuming process {paused_process.name}")
                paused_process = None
            time.sleep(10)  # Check system resources every 10 seconds
        
        # Monitor the processes for max_runtime and kill if necessary
        for p in processes:
            if not p.is_alive():
                continue  # Skip already finished processes

            # Calculate elapsed time for running processes
            elapsed_time = time.time() - start_times[p]
            # If a process has been running for longer than max_runtime (5 minutes)
            if elapsed_time > max_runtime:
                logging.warning(f"Process {p.name} exceeded {max_runtime/60} minutes, killing process.")
                p.terminate()  # Terminate the process
                processes.remove(p)  # Remove the process from the list
                break  # Exit the loop as we killed one process
 
def currentDayProcessed(product_ids):
    """
    Saving today's Processed products
    """
    scrapedCountFile = f"({date.today()})Processed"
    if os.path.exists(scrapedCountFile):
        with open(scrapedCountFile, "a") as f:
            f.write(str(product_ids) + "\n")
    else:
        with open(scrapedCountFile, "w") as f:
            f.write(str(product_ids) + "\n")

# Main function to manage the scraping
def main():
    # Get products from DB
    params = getKeywordFromDB()
    searchKeys, productIDs, productURLs = params
    if len(searchKeys) == 0:
        print("Not found products to find GCODE")
        return
    
    logger.debug(f"""
    -------------- Process started for {len(searchKeys)} product(s) --------------
    """)
    # Begin scraping products
    processes, pause_events = [], []
    for searchKey in searchKeys:
        p = multiprocessing.Process(target=scrapperCore, args=(searchKey, productIDs, productURLs))
        event = multiprocessing.Event()
        pause_events.append(event)
        event.set()
        processes.append(p)
        p.start()

    # Monitor resources
    monitor_resources(processes, pause_events)
    # Wait for all processes to complete
    for p in processes:
        p.join()


if __name__ == "__main__":
    # receivers = ['amankumar.matrid34567@gmail.com']
    # receivers = ['aspdnsf.skin@gmail.com', 'vijeta.matrid3@gmail.com', 'amritpal.matrid78699@gmail.com', 'amankumar.matrid34567@gmail.com']
    start = time.perf_counter()
    main()
    finish = time.perf_counter()
    logger.debug(f'Finished ThreadMain in {round(finish - start, 2)} second(s)')