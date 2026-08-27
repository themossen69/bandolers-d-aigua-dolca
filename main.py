import threading
import time
import os
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from scheduler.scheduler import ini_scheduler

private_path = os.path.abspath(os.path.join(os.getcwd(), "..", "_private"))
if private_path not in sys.path:
    sys.path.insert(0, private_path)
from constants import ADMIN_ID

from bot_func import bot
from functions import create_DB, create_var_DB, create_controls_bandolers_DB, create_controls_DB, execute_db, db_worker 

worker_thread = threading.Thread(target=db_worker, daemon=True)
worker_thread.start()

# si no existeixen les taules crear-les (ja comprova si existeix la taula)
execute_db(create_DB)
execute_db(create_var_DB)

execute_db(create_controls_DB, "controls.csv") 
execute_db(create_controls_bandolers_DB)

# MAIN
if __name__ == "__main__":
    scheduler = ini_scheduler(bot, ADMIN_ID)
    scheduler.remove_all_jobs()
    print("tasques en memòria:")
    scheduler.print_jobs()
    print()
    bot.send_message(ADMIN_ID, "El bot s'ha iniciat correctament.\n/estat_bot per veure l'estat del bot.")
    try:  
        bot.polling(timeout=120, skip_pending=True)  # polling amb timeout per evitar col·lisions entre usuaris
    except Exception as e:
        error = f"S'ha produït un error: {e}"
        print(error)
        bot.send_message(ADMIN_ID, error)
        time.sleep(5)  # comprova missatges per sempre
    finally:
        scheduler.shutdown()