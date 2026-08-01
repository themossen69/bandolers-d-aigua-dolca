import time
from datetime import datetime
from scheduler.database import  get_users, get_users_with_no_control, get_users_with_no_control, get_users_with_no_day_controls, get_last_day_control, get_final_date_control, is_it_the_last_control_of_the_day
from functions import data_strip, next_control_message, get_next_control, execute_db, get_inscripcio_disponible, change_inscripcio_disponible, set_winner, update_state_and_kills_2_start, assign_victims_cyclic, get_path_messages, file_content_2_string, send_message_to_target

def get_control_id_from_task_name(task_name: str) -> str | None:
    """
    Funció que extreu l'ID del control a partir del nom de la tasca.
    """
    if task_name.startswith("inici_control_"):
        return task_name.replace("inici_control_", "")
    elif task_name.startswith("final_control_"):
        return task_name.replace("final_control_", "")
    elif task_name.startswith("avis_final_control_"):
        return task_name.replace("avis_final_control_", "")
    else:
        return None

def is_control(task_name: str) -> bool:
    """
    Funció que comprova si el nom de la tasca correspon a un control.
    """
    return True if get_control_id_from_task_name(task_name) else False

def handle_task(bot, task_name, ADMIN_ID):
    """
    Funció que maneja les tasques programades segons el nom de la tasca.
    """
    print(f"Executant tasca: {task_name} a les {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    bool_control = is_control(task_name)
    print(f"bool_control: {bool_control}")
    print(f"task_name: {task_name}")

    users = []
    msg_list = []

    if bool_control:
        """
        users = [(user_id: int, has_day_controls: bool)] on si l'usuari té el control assignat o no
        """
        control_id = get_control_id_from_task_name(task_name)
        final_date = execute_db(get_final_date_control, control_id)
        day, month, year, hour, minute, second = data_strip(final_date)
        next_control = execute_db(get_next_control, control_id)

        bool_last_control = execute_db(is_it_the_last_control_of_the_day, control_id)
        users_with_no_control = execute_db(get_users_with_no_day_controls, control_id)
        users = [(user_id, not user_id in users_with_no_control) for user_id in execute_db(get_users)]

        if task_name.startswith("inici_control_"):
            msg_list = [f"Comença el control {control_id.upper()}.\nEs pot completar fins a les {hour}:{minute} del {day}/{month}/{year}."]
            
            if bool_last_control:
                msg_list.append("Avís: És l'últim control del dia, si no el fas, quedaràs declarat fugitiu i seràs eliminat del joc.")

        elif task_name.startswith("final_control_"):
            msg_list = [f"El control {control_id.upper()} ha finalitzat."]
            if bool_last_control:
                msg_list = ["L'últim control del dia ha finalitzat."]
                msg_list.append("ATENCIÓ: No has fet cap control del dia, ets declarat fugitiu. Gràcies per participar!")
                # TODO: gestionar l'eliminació
            
            if next_control:
                msg_list[0] += next_control_message(next_control["inici"], next_control["final"])

        for user_id, has_day_controls in users:
            try:
                if has_day_controls:
                    bot.send_message(user_id, msg_list[0])
                else:
                    bot.send_message(user_id, "\n".join(msg_list))
                time.sleep(0.05)  # Petita pausa per evitar problemes amb l'enviament massiu
            except Exception as e:
                error_msg = f"Error enviant missatge d'inici de control a l'usuari {user_id}: {e}"
                print(error_msg)
                bot.send_message(ADMIN_ID, error_msg)

    else:
        match task_name:
            case "obrir-inscripcions":
                valor = execute_db(get_inscripcio_disponible)
                if not valor:
                    execute_db(change_inscripcio_disponible)
                    msg = "Les inscripcions s'han obert. Ara els usuaris poden registrar-se.\n"
                else:
                    msg = "Les inscripcions ja estan obertes.\n"
                bot.send_message(ADMIN_ID, msg)

            case "comencar-joc":
                execute_db(update_state_and_kills_2_start)
                execute_db(set_winner, 0)  # Resetejar guanyador
                # Tancar inscripcions
                if execute_db(get_inscripcio_disponible):
                    execute_db(change_inscripcio_disponible)
                # Assignar víctimes
                execute_db(assign_victims_cyclic, timeout=20)
                msg_admin = "S'han assignat les víctimes de manera cíclica.\n\n"
                msg_admin += "Per veure el cicle prem /cicle_bandolers."
                bot.send_message(ADMIN_ID, msg_admin)
                
                msg_admin = "S'han posat a tots els usuaris com a jugant amb 0 kills i s'han assignat les víctimes.\n/usuaris per veure els usuaris registrats.\n\n"
                msg_admin += "El joc ha començat!"
                bot.send_message(ADMIN_ID, msg_admin)
                send_message_to_target('Tots els usuaris', file_content_2_string(get_path_messages("start.txt")), bot)

            case "acabar-joc":
                # TODO: gestionar final del joc
                if execute_db(user_with_themselves_as_victim):
                    

def get_last_job(scheduler):
    """
    Funció que retorna l'última tasca programada al scheduler.
    """
    jobs = scheduler.get_jobs()
    if jobs:
        last_job = max(jobs, key=lambda job: job.next_run_time)
        return last_job
    return None

def get_last_job_task_id(scheduler) -> int:
    """
    Funció que retorna l'ID de l'última tasca programada al scheduler.
    """
    last_job = get_last_job(scheduler)
    task_id = last_job.id if last_job else None
    return int(task_id.split("_")[1]) if task_id else None

def add_new_task_to_scheduler(scheduler, bot, task_name, scheduled_time, ADMIN_ID):
    """
    Funció que afegeix una nova tasca al scheduler.
    """
    run_date = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")

    scheduler.add_job(
        handle_task,
        trigger='date',
        run_date=run_date,
        args=[bot, task_name, ADMIN_ID],
        id=f"task_{get_last_job_task_id(scheduler) + 1 if get_last_job_task_id(scheduler) is not None else 100}"
    )