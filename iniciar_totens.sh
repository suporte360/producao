#!/bin/bash
# Iniciar todos os totens de produção
# Uso: bash iniciar_totens.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/totens_start.log"

echo "[$(date)] Iniciando totens..." | tee "$LOG"

# Função para iniciar um totem
start_totem() {
    local SETOR=$1
    local PORTA=$2

    # Verifica se já está rodando
    if lsof -ti:$PORTA > /dev/null 2>&1; then
        echo "  [$PORTA] $SETOR já está rodando (PID $(lsof -ti:$PORTA)). Reiniciando..."
        kill $(lsof -ti:$PORTA) 2>/dev/null
        sleep 1
    fi

    cd "$DIR"
    SETOR=$SETOR PORT=$PORTA nohup python3 totem_setor.py > "totem_${PORTA}.log" 2>&1 &
    local PID=$!
    sleep 1

    if kill -0 $PID 2>/dev/null; then
        echo "  [$PORTA] $SETOR iniciado (PID $PID) ✓" | tee -a "$LOG"
    else
        echo "  [$PORTA] $SETOR FALHOU ao iniciar ✗" | tee -a "$LOG"
    fi
}

# 5003 - Serralheria (original)
if [ -f "$DIR/serralheria_tomem.py" ]; then
    start_totem_serralheria() {
        local PORTA=5003
        if lsof -ti:$PORTA > /dev/null 2>&1; then
            echo "  [$PORTA] Serralheria já está rodando. Reiniciando..."
            kill $(lsof -ti:$PORTA) 2>/dev/null
            sleep 1
        fi
        cd "$DIR"
        nohup python3 serralheria_tomem.py > "totem_5003.log" 2>&1 &
        local PID=$!
        sleep 1
        if kill -0 $PID 2>/dev/null; then
            echo "  [$PORTA] Serralheria iniciado (PID $PID) ✓" | tee -a "$LOG"
        else
            echo "  [$PORTA] Serralheria FALHOU ✗" | tee -a "$LOG"
        fi
    }
    start_totem_serralheria
fi

# 5004 - Pintura
start_totem "PINTURA" 5004

# 5005 - Montagem
start_totem "MONTAGEM" 5005

# 5006 - Embalagem
start_totem "EMBALAGEM" 5006

echo "" | tee -a "$LOG"
echo "[$(date)] Totens iniciados. Verifique os logs:" | tee -a "$LOG"
echo "  Serralheria: tail -f $DIR/totem_5003.log" | tee -a "$LOG"
echo "  Pintura:     tail -f $DIR/totem_5004.log" | tee -a "$LOG"
echo "  Montagem:    tail -f $DIR/totem_5005.log" | tee -a "$LOG"
echo "  Embalagem:   tail -f $DIR/totem_5006.log" | tee -a "$LOG"