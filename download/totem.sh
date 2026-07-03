#!/bin/bash
# Script para iniciar/parar/reiniciar o Serralheria Totem (porta 5003)
# Uso: ./totem.sh start | stop | restart | status | log

APP_DIR="/home/z/my-project/producao"
APP_FILE="$APP_DIR/serralheria_tomem.py"
PID_FILE="/tmp/serralheria_tomem.pid"
LOG_FILE="/tmp/serralheria_tomem.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[JA RODANDO] PID $(cat $PID_FILE)"
        return 1
    fi
    echo "[INICIANDO] Serralheria Totem..."
    cd "$APP_DIR"
    nohup python3 "$APP_FILE" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[OK] Rodando PID $(cat $PID_FILE) - http://0.0.0.0:5003"
    else
        echo "[ERRO] Falha ao iniciar. Veja $LOG_FILE"
        rm -f "$PID_FILE"
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "[PARADO] Nenhum PID encontrado"
        return 1
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        sleep 1
        echo "[OK] Processo $PID finalizado"
    else
        echo "[JA PARADO] PID $PID nao existe"
    fi
    rm -f "$PID_FILE"
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[ATIVO] PID $(cat $PID_FILE) - http://0.0.0.0:5003"
    else
        echo "[PARADO]"
        rm -f "$PID_FILE"
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    log)     tail -30 "$LOG_FILE" ;;
    *)       echo "Uso: $0 {start|stop|restart|status|log}" ;;
esac