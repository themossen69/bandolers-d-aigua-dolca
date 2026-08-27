from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from scheduler.database import get_tasks
from scheduler.tasks import handle_task
from functions import execute_db


def ini_scheduler(bot, ADMIN_ID):
    """Inicialitza el programador amb les hores guardades a la BD."""
    scheduler = BackgroundScheduler()
    tasks = get_tasks("./scheduler/horaris.csv")  

    # Programem una tasca per a cada horari trobat a la BD
    for task_id, task_name, scheduled_time in tasks:
        run_date = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")

        scheduler.add_job(
            handle_task,
            trigger='date',
            run_date=run_date,
            args=[bot, task_name, ADMIN_ID],
            id=f"task_{task_id}"
        )
        date = run_date.strftime("%Y-%m-%d %H:%M:%S")
        print(f"⏰ {date} - {task_name} programada a les {run_date.hour:02d}:{run_date.minute:02d}")

    scheduler.start()
    return scheduler