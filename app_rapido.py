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

print("🚀 YOUTUBE AUDIO API - ULTRA RESISTENTE (Anti-Bot Avançado)")

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILES_DIR = os.path.join(BASE_DIR, 'audio_files')
TEMP_DIR = os.path.join(BASE_DIR, 'temp_downloads')
os.makedirs(AUDIO_FILES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# CONFIGURAÇÕES ANTI-BOT AVANÇADAS
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def sanitizar_nome_arquivo(nome):
    if not nome: return None
    nome = re.sub(r'[^\w\s\-_]', '', nome)
    nome = nome.replace(' ', '_')
    return nome[:50]

def obter_configuracao_antibot(tentativa_num):
    """Configurações específicas para evitar detecção como bot"""
    
    configs = [
        # TENTATIVA 1: Configuração mais stealth
        {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['dash', 'hls']
                }
            }
        },
        # TENTATIVA 2: Configuração mobile
        {
            'format': 'bestaudio[ext=webm]/bestaudio/best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.youtube.com/',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['dash']
                }
            }
        },
        # TENTATIVA 3: Configuração mínima
        {
            'format': 'bestaudio/best',
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': '*/*',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                }
            }
        },
        # TENTATIVA 4: Último recurso - qualquer formato
        {
            'format': 'best',
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
            }
        }
    ]
    
    base_config = {
        'socket_timeout': 30,
        'retries': 15,
        'fragment_retries': 15,
        'skip_unavailable_fragments': True,
        'continue_dl': True,
        'nooverwrites': True,
        'quiet': True,  # Mais stealth
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': False,
        'force_ipv4': True,
        'throttled_rate': '1M',
    }
    
    if tentativa_num < len(configs):
        base_config.update(configs[tentativa_num])
    
    return base_config

def extrair_info_video_sem_download(url):
    """Tenta extrair informações sem download primeiro"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'ignoreerrors': True,
            'http_headers': {'User-Agent': random.choice(USER_AGENTS)},
            'socket_timeout': 15
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.warning(f"⚠️  Não foi possível extrair info: {e}")
        return None

def baixar_com_tentativas_avancado(url, id_processo, tentativas=4):
    """Sistema avançado de tentativas com estratégias diferentes"""
    
    # Primeiro tenta obter informações básicas
    info = extrair_info_video_sem_download(url)
    if info:
        logger.info(f"📊 Vídeo detectado: {info.get('title', 'N/A')}")
    
    for tentativa in range(tentativas):
        try:
            logger.info(f"🔄 Tentativa {tentativa + 1}/{tentativas} para {id_processo}")
            
            # Pausa estratégica entre tentativas
            if tentativa > 0:
                wait_time = tentativa * 3 + random.randint(1, 5)
                logger.info(f"⏳ Aguardando {wait_time}s...")
                time.sleep(wait_time)
            
            ydl_opts = obter_configuracao_antibot(tentativa)
            ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'temp_{id_processo}_{tentativa}.%(ext)s')
            
            logger.info(f"🔧 Usando estratégia {tentativa + 1}...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_completo = ydl.extract_info(url, download=True)
            
            # Verificar se o arquivo foi baixado
            for arquivo in os.listdir(TEMP_DIR):
                if f'temp_{id_processo}_{tentativa}' in arquivo:
                    arquivo_path = os.path.join(TEMP_DIR, arquivo)
                    if os.path.exists(arquivo_path) and os.path.getsize(arquivo_path) > 1000:  # Mínimo 1KB
                        tamanho = os.path.getsize(arquivo_path) / (1024 * 1024)
                        logger.info(f"✅ Tentativa {tentativa + 1} BEM-SUCEDIDA: {tamanho:.2f} MB")
                        return arquivo_path, info_completo.get('title', 'Áudio')
                    else:
                        logger.warning(f"⚠️  Arquivo muito pequeno ou inválido, tentando próximo método...")
                        os.remove(arquivo_path)
                        continue
                        
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"❌ Tentativa {tentativa + 1} falhou: {error_msg}")
            
            # Análise do erro para estratégia
            if "Sign in to confirm you're not a bot" in error_msg:
                logger.info("🎯 Detectado bloqueio 'not a bot', aumentando delay...")
                time.sleep(10)  # Delay maior para este erro específico
            continue
    
    # SE CHEGOU AQUI, TODAS AS TENTATIVAS FALHARAM
    raise Exception(f"❌ Todas as {tentativas} tentativas falharam. Possíveis causas:\n"
                   "• Bloqueio temporário do YouTube\n"
                   "• Vídeo com restrições\n"
                   "• Problema de rede\n"
                   "Tente novamente em alguns minutos ou use outro vídeo.")

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
        logger.info(f"🎬 INICIANDO PROCESSAMENTO {id_processo}")
        logger.info(f"🔗 URL: {url}")
        logger.info(f"⏰ Corte: {inicio_segundos}s a {fim_segundos}s")
        
        # Validar parâmetros
        if fim_segundos <= inicio_segundos:
            raise Exception("Tempo final deve ser maior que o inicial")
        
        if fim_segundos - inicio_segundos > 7200:  # 2 horas max
            raise Exception("Corte máximo de 2 horas")
        
        # 1. BAIXAR COM SISTEMA AVANÇADO DE TENTATIVAS
        logger.info("📥 INICIANDO DOWNLOAD (Sistema Anti-Bot)...")
        arquivo_temp, titulo = baixar_com_tentativas_avancado(url, id_processo, tentativas=4)
        
        # 2. PREPARAR NOME DO ARQUIVO
        if nome_arquivo and nome_arquivo.strip():
            nome_base = sanitizar_nome_arquivo(nome_arquivo)
            nome_final = f"{nome_base}_{id_processo}.mp3"
        else:
            nome_base = sanitizar_nome_arquivo(titulo) or f"audio_{id_processo}"
            nome_final = f"{nome_base}.mp3"
        
        arquivo_final = os.path.join(AUDIO_FILES_DIR, nome_final)
        
        # 3. APLICAR CORTE PRECISO
        logger.info("🔧 APLICANDO CORTE TEMPORAL...")
        cortar_audio_preciso(arquivo_temp, arquivo_final, inicio_segundos, fim_segundos)
        
        # 4. VERIFICAR RESULTADO
        if not os.path.exists(arquivo_final):
            raise Exception("Arquivo final não criado")
        
        tamanho_final = os.path.getsize(arquivo_final) / (1024 * 1024)
        duracao_corte = fim_segundos - inicio_segundos
        
        logger.info(f"🎉 PROCESSO {id_processo} CONCLUÍDO COM SUCESSO!")
        logger.info(f"📁 Arquivo: {nome_final}")
        logger.info(f"📏 Tamanho: {tamanho_final:.2f} MB")
        logger.info(f"⏱️  Duração do corte: {duracao_corte}s")
        
        return {
            'sucesso': True,
            'arquivo': nome_final,
            'tamanho_mb': round(tamanho_final, 2),
            'duracao_corte': duracao_corte
        }
        
    except Exception as e:
        logger.error(f"❌ ERRO NO PROCESSAMENTO {id_processo}: {e}")
        return {'sucesso': False, 'erro': str(e)}
    finally:
        # LIMPEZA COMPLETA
        if arquivo_temp and os.path.exists(arquivo_temp):
            try:
                os.remove(arquivo_temp)
                logger.info("🧹 Arquivo temporário removido")
            except:
                pass
        
        # Limpar TODOS os arquivos temporários deste processo
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
        'mensagem': 'YouTube Audio API - Ultra Resistente',
        'status': '🟢 Online',
        'versao': '3.0',
        'recursos': [
            'Sistema Anti-Bot Avançado',
            '4 Estratégias de Download',
            'Corte Temporal Preciso',
            'Limpeza Automática'
        ]
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
        
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return jsonify({'erro': 'URL do YouTube inválida'}), 400
        
        if fim <= inicio:
            return jsonify({'erro': 'Tempo final deve ser maior que o inicial'}), 400
        
        id_processo = str(uuid.uuid4())[:8]
        
        logger.info(f"📋 NOVO PROCESSO: {id_processo}")
        logger.info(f"🌐 URL: {url[:50]}...")
        logger.info(f"⏰ Corte: {inicio}s - {fim}s")
        
        thread = threading.Thread(
            target=executar_processamento_definitivo,
            args=(url, inicio, fim, id_processo, nome_arquivo)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'sucesso': True,
            'id_processo': id_processo,
            'mensagem': 'Processamento iniciado com sistema anti-bot',
            'detalhes': {
                'inicio_segundos': inicio,
                'fim_segundos': fim,
                'duracao_corte': fim - inicio,
                'estrategias': 4
            }
        })
        
    except Exception as e:
        logger.error(f"💥 Erro em /api/processar: {e}")
        return jsonify({'erro': str(e)}), 500

def executar_processamento_definitivo(url, inicio, fim, id_processo, nome_arquivo):
    """Wrapper para execução em thread"""
    try:
        resultado = processar_audio_definitivo(url, inicio, fim, id_processo, nome_arquivo)
        if resultado['sucesso']:
            logger.info(f"🎉 {id_processo} - CONCLUÍDO COM SUCESSO!")
        else:
            logger.error(f"❌ {id_processo} - FALHOU: {resultado['erro']}")
    except Exception as e:
        logger.error(f"💥 {id_processo} - ERRO CRÍTICO: {e}")

@app.route('/api/status/<id_processo>')
def verificar_status(id_processo):
    try:
        # Verificar se já está concluído
        for arquivo in os.listdir(AUDIO_FILES_DIR):
            if id_processo in arquivo and arquivo.endswith('.mp3'):
                caminho = os.path.join(AUDIO_FILES_DIR, arquivo)
                tamanho = os.path.getsize(caminho) / (1024 * 1024)
                return jsonify({
                    'sucesso': True,
                    'status': 'concluido',
                    'arquivo': arquivo,
                    'tamanho_mb': round(tamanho, 2),
                    'download_url': f'/api/download/{id_processo}'
                })
        
        # Verificar se está processando (arquivos temporários)
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
            if id_processo in arquivo and arquivo.endswith('.mp3'):
                caminho_arquivo = os.path.join(AUDIO_FILES_DIR, arquivo)
                return send_file(
                    caminho_arquivo,
                    as_attachment=True,
                    download_name=arquivo
                )
        return jsonify({'erro': 'Arquivo não encontrado'}), 404
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/limpar', methods=['POST'])
def limpar_arquivos():
    """Limpa arquivos temporários"""
    try:
        arquivos_removidos = 0
        for pasta in [TEMP_DIR, AUDIO_FILES_DIR]:
            for arquivo in os.listdir(pasta):
                try:
                    os.remove(os.path.join(pasta, arquivo))
                    arquivos_removidos += 1
                except:
                    pass
        return jsonify({'sucesso': True, 'mensagem': f'{arquivos_removidos} arquivos removidos'})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*60)
    print("🚀 YOUTUBE AUDIO API - ULTRA RESISTENTE")
    print("="*60)
    print("🛡️  Sistema Anti-Bot Avançado Ativado")
    print("🎯 4 Estratégias de Download")
    print("✂️  Corte Temporal Preciso")
    print("🧹 Limpeza Automática")
    print("="*60)
    print(f"🌐 Servidor iniciando na porta {port}...")
    print("="*60)

    app.run(host='0.0.0.0', port=port, debug=False)
