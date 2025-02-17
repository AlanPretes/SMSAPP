import subprocess
import time


def collect_adb_sms_log():
    """ Coleta o log completo do SMS via ADB para análise """
    comando = 'adb shell content query --uri content://sms'
    resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
    
    with open('sms_log.txt', 'w') as log_file:
        log_file.write(resultado.stdout)

    print("Log coletado e salvo em sms_log.txt")


if __name__ == "__main__":
    collect_adb_sms_log()