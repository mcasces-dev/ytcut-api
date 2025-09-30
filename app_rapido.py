import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import uuid
import threading
import subprocess
import re
import time
import random

print("🚀 YOUTUBE AUDIO API - DEFINITIVO (Corte + Anti-Bloqueio)")

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILES_DIR = os.path.join(BASE_DIR, 'audio_files')
TEMP_DIR = os.path.join(BASE_DIR, 'temp_downloads')
os.makedirs(AUDIO_FILES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Configurações anti-bloqueio
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0'
]

def sanitizar_nome_arquivo(nome):
    if not nome: return None
    nome = re.sub(r'[^\w\s\-_]', '', nome)
    nome = nome.replace(' ', '_')
    return nome[:50]

def obter_configuracao_antiblok(tentativa_num):
    """Configurações diferentes para cada tentativa"""
    configs = [
        # Tentativa 1: Formato mais compatível
        {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'http_headers': {'User-Agent': random.choice(USER_AGENTS)}
        },
        # Tentativa 2: WebM
        {
            'format': 'bestaudio[ext=webm]/bestaudio/best',
            'http_headers': {'User-Agent': random.choice(USER_AGENTS)}
        },
        # Tentativa 3: Qualquer áudio
        {
            'format': 'bestaudio/best',
            'http_headers': {'User-Agent': random.choice(USER_AGENTS)}
        },
        # Tentativa 4: Vídeo de baixa resolução
        {
            'format': 'best[height<=360]/best',
            'http_headers': {'User-Agent': random.choice(USER_AGENTS)}
        }
    ]
    
    base_config = {
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'continue_dl': True,
        'nooverwrites': True,
        'quiet': False,
        'no_warnings': False,
    }
    
    base_config.update(configs[tentativa_num % len(configs)])
    return base_config

def baixar_com_tentativas(url, id_processo, tentativas=4):
    """Tenta baixar com múltiplas estratégias"""
    for tentativa in range(tentativas):
        try:
            logger.info(f"🔄 Tentativa {tentativa + 1}/{tentativas}...")
            
            # Pequena pausa entre tentativas
            if tentativa > 0:
                wait_time = tentativa * 2  # 2, 4, 6 segundos
                logger.info(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
                time.sleep(wait_time)
            
            ydl_opts = obter_configuracao_antiblok(tentativa)
            ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'temp_{id_processo}_{tentativa}.%(ext)s')
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
            # Encontrar arquivo baixado
            for arquivo in os.listdir(TEMP_DIR):
                if f'temp_{id_processo}_{tentativa}' in arquivo:
                    arquivo_path = os.path.join(TEMP_DIR, arquivo)
                    tamanho = os.path.getsize(arquivo_path) / (1024 * 1024)
                    logger.info(f"✅ Tentativa {tentativa + 1} bem-sucedida: {tamanho:.2f} MB")
                    return arquivo_path, info.get('title', 'Áudio')
                    
        except Exception as e:
            logger.warning(f"❌ Tentativa {tentativa + 1} falhou: {str(e)}")
            continue
    
    raise Exception(f"Todas as {tentativas} tentativas de download falharam")

def cortar_audio_preciso(arquivo_entrada, arquivo_saida, inicio_segundos, fim_segundos):
    """Corte temporal preciso com FFmpeg"""
    try:
        duracao = fim_segundos - inicio_segundos
        logger.info(f"✂️  Cortando: {inicio_segundos}s → {fim_segundos}s ({duracao}s)")
        
        # COMANDO 1: Corte rápido com cópia
        comando = [
            'ffmpeg', '-i', arquivo_entrada,
            '-ss', str(inicio_segundos), '-to', str(fim_segundos),
            '-c', 'copy', '-y', '-hide_banner', '-loglevel', 'error',
            arquivo_saida
        ]
        
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=120)
        
        if resultado.returncode == 0 and os.path.exists(arquivo_saida):
            tamanho = os.path.getsize(arquivo_saida) / (1024 * 1024)
            logger.info(f"✅ Corte rápido: {tamanho:.2f} MB")
            return True
        
        # COMANDO 2: Com recompressão
        comando = [
            'ffmpeg', '-i', arquivo_entrada,
            '-ss', str(inicio_segundos), '-to', str(fim_segundos),
            '-c:a', 'libmp3lame', '-b:a', '192k', '-y',
            '-hide_banner', '-loglevel', 'error',
            arquivo_saida
        ]
        
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)
        
        if resultado.returncode == 0 and os.path.exists(arquivo_saida):
            tamanho = os.path.getsize(arquivo_saida) / (1024 * 1024)
            logger.info(f"✅ Corte com recompressão: {tamanho:.2f} MB")
            return True
            
        raise Exception(f"FFmpeg falhou: {resultado.stderr}")
        
    except subprocess.TimeoutExpired:
        raise Exception("Timeout no corte")
    except Exception as e:
        raise Exception(f"Erro no corte: {e}")

def processar_audio_definitivo(url, inicio_segundos, fim_segundos, id_processo, nome_arquivo=None):
    """Processamento definitivo com todas as otimizações"""
    arquivo_temp = None
    try:
        logger.info(f"🎬 Iniciando processamento {id_processo}")
        
        # Validar parâmetros
        if fim_segundos <= inicio_segundos:
            raise Exception("Tempo final deve ser maior que o inicial")
        
        if fim_segundos - inicio_segundos > 7200:  # 2 horas max
            raise Exception("Corte máximo de 2 horas")
        
        # 1. BAIXAR COM MÚLTIPLAS TENTATIVAS
        logger.info("📥 Iniciando download com tentativas...")
        arquivo_temp, titulo = baixar_com_tentativas(url, id_processo, tentativas=4)
        
        # 2. PREPARAR NOME DO ARQUIVO
        if nome_arquivo and nome_arquivo.strip():
            nome_base = sanitizar_nome_arquivo(nome_arquivo)
            nome_final = f"{nome_base}_{id_processo}.mp3"
        else:
            nome_base = sanitizar_nome_arquivo(titulo) or f"audio_{id_processo}"
            nome_final = f"{nome_base}.mp3"
        
        arquivo_final = os.path.join(AUDIO_FILES_DIR, nome_final)
        
        # 3. APLICAR CORTE PRECISO
        logger.info("🔧 Aplicando corte temporal...")
        cortar_audio_preciso(arquivo_temp, arquivo_final, inicio_segundos, fim_segundos)
        
        # 4. VERIFICAR RESULTADO
        if not os.path.exists(arquivo_final):
            raise Exception("Arquivo final não criado")
        
        tamanho_final = os.path.getsize(arquivo_final) / (1024 * 1024)
        duracao_corte = fim_segundos - inicio_segundos
        
        logger.info(f"🎉 PROCESSO CONCLUÍDO!")
        logger.info(f"📁 Arquivo: {nome_final}")
        logger.info(f"📏 Tamanho: {tamanho_final:.2f} MB")
        logger.info(f"⏱️  Corte: {inicio_segundos}s a {fim_segundos}s ({duracao_corte}s)")
        
        return {
            'sucesso': True,
            'arquivo': nome_final,
            'tamanho_mb': round(tamanho_final, 2),
            'duracao_corte': duracao_corte
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento: {e}")
        return {'sucesso': False, 'erro': str(e)}
    finally:
        # Limpeza completa
        if arquivo_temp and os.path.exists(arquivo_temp):
            try:
                os.remove(arquivo_temp)
                logger.info("🧹 Arquivo temporário removido")
            except:
                pass
        
        # Limpar outros arquivos temporários
        for arquivo in os.listdir(TEMP_DIR):
            if f"temp_{id_processo}" in arquivo:
                try:
                    os.remove(os.path.join(TEMP_DIR, arquivo))
                except:
                    pass

# ROTAS OTIMIZADAS
@app.route('/')
def home():
    return jsonify({
        'mensagem': 'YouTube Audio API - Definitiva',
        'status': '🟢 Online',
        'recursos': ['Corte preciso', '4 tentativas', 'Anti-bloqueio']
    })

@app.route('/api/processar', methods=['POST'])
def processar_audio():
    try:
        dados = request.get_json()
        url = dados.get('url', '').strip()
        inicio = int(dados.get('inicio', 0))
        fim = int(dados.get('fim', 30))
        nome_arquivo = dados.get('nome_arquivo', '').strip()
        
        if not url:
            return jsonify({'erro': 'URL é obrigatória'}), 400
        
        if fim <= inicio:
            return jsonify({'erro': 'Tempo final deve ser maior'}), 400
        
        id_processo = str(uuid.uuid4())[:8]
        
        logger.info(f"📋 Novo processo: {id_processo}")
        
        thread = threading.Thread(
            target=executar_processamento_definitivo,
            args=(url, inicio, fim, id_processo, nome_arquivo)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'sucesso': True,
            'id_processo': id_processo,
            'mensagem': 'Processamento iniciado (4 tentativas)',
            'detalhes': {'inicio': inicio, 'fim': fim, 'duracao': fim - inicio}
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

def executar_processamento_definitivo(url, inicio, fim, id_processo, nome_arquivo):
    """Wrapper para execução em thread"""
    try:
        resultado = processar_audio_definitivo(url, inicio, fim, id_processo, nome_arquivo)
        if resultado['sucesso']:
            logger.info(f"🎉 {id_processo} - SUCESSO!")
        else:
            logger.error(f"❌ {id_processo} - FALHA: {resultado['erro']}")
    except Exception as e:
        logger.error(f"💥 {id_processo} - ERRO CRÍTICO: {e}")

@app.route('/api/status/<id_processo>')
def verificar_status(id_processo):
    try:
        for arquivo in os.listdir(AUDIO_FILES_DIR):
            if f"_{id_processo}.mp3" in arquivo:
                caminho = os.path.join(AUDIO_FILES_DIR, arquivo)
                return jsonify({
                    'sucesso': True,
                    'status': 'concluido',
                    'arquivo': arquivo,
                    'download_url': f'/api/download/{id_processo}'
                })
        
        # Verificar se está processando
        for arquivo in os.listdir(TEMP_DIR):
            if f"temp_{id_processo}" in arquivo:
                return jsonify({
                    'sucesso': True,
                    'status': 'processando',
                    'mensagem': 'Download em andamento...'
                })
        
        return jsonify({
            'sucesso': True,
            'status': 'processando', 
            'mensagem': 'Iniciando processamento...'
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/download/<id_processo>')
def download_audio(id_processo):
    try:
        for arquivo in os.listdir(AUDIO_FILES_DIR):
            if f"_{id_processo}.mp3" in arquivo:
                return send_file(
                    os.path.join(AUDIO_FILES_DIR, arquivo),
                    as_attachment=True,
                    download_name=arquivo
                )
        return jsonify({'erro': 'Arquivo não encontrado'}), 404
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    # Obter porta das variáveis de ambiente (Render usa PORT)
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Servidor definitivo na porta 5000...")
    print("💡 Agora com: 4 tentativas + Corte preciso + Anti-bloqueio")

    app.run(host='0.0.0.0', port=port, debug=True)
