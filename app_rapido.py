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
import requests

print("🚀 YOUTUBE AUDIO API - SOLUÇÃO DEFINITIVA (Contorno Total de Bloqueios)")

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILES_DIR = os.path.join(BASE_DIR, 'audio_files')
TEMP_DIR = os.path.join(BASE_DIR, 'temp_downloads')
os.makedirs(AUDIO_FILES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# SISTEMA DE USER AGENTS E CONFIGURAÇÕES AVANÇADADAS
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
]

def sanitizar_nome_arquivo(nome):
    if not nome: return None
    nome = re.sub(r'[^\w\s\-_]', '', nome)
    nome = nome.replace(' ', '_')
    return nome[:50]

def obter_configuracao_extrema(tentativa_num):
    """Configurações extremas para contornar qualquer bloqueio"""
    
    configs = [
        # TENTATIVA 1: Configuração Stealth Completa
        {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,pt;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs', 'webpage'],
                    'skip': ['dash', 'hls']
                }
            },
            'postprocessor_args': {'ffmpeg': ['-hide_banner']},
        },
        # TENTATIVA 2: Modo Mobile Agressivo
        {
            'format': 'bestaudio[ext=webm]/bestaudio/best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'X-Requested-With': 'com.google.android.youtube',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['configs', 'webpage', 'js'],
                }
            }
        },
        # TENTATIVA 3: Configuração Minimalista
        {
            'format': 'worstaudio/worst',
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': '*/*',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'player_skip': ['configs', 'webpage', 'js', 'token'],
                }
            }
        },
        # TENTATIVA 4: Último Recurso - Força Bruta
        {
            'format': 'best',
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
            },
            'ignoreerrors': True,
            'no_check_certificate': True,
            'prefer_insecure': True,
        }
    ]
    
    base_config = {
        'socket_timeout': 45,
        'retries': 20,
        'fragment_retries': 20,
        'skip_unavailable_fragments': True,
        'continue_dl': True,
        'nooverwrites': True,
        'noprogress': True,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': False,
        'force_ipv4': True,
        'throttled_rate': '512K',
        'buffersize': 1024 * 32,
        'http_chunk_size': 10485760,
    }
    
    if tentativa_num < len(configs):
        base_config.update(configs[tentativa_num])
    
    return base_config

def verificar_url_alternativa(video_id):
    """Tenta acessar o vídeo por URLs alternativas"""
    alternativas = [
        f'https://yewtu.be/watch?v={video_id}',
        f'https://invidious.snopyta.org/watch?v={video_id}',
        f'https://youtube.com/watch?v={video_id}',
        f'https://www.youtube-nocookie.com/embed/{video_id}',
    ]
    
    for url in alternativas:
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': random.choice(USER_AGENTS)
            })
            if response.status_code == 200:
                logger.info(f"✅ URL alternativa funcionando: {url}")
                return url
        except:
            continue
    
    return None

def extrair_video_id(url):
    """Extrai o ID do vídeo da URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def baixar_com_estrategia_extrema(url, id_processo, tentativas=6):
    """Sistema extremo de download com múltiplas estratégias"""
    
    video_id = extrair_video_id(url)
    if video_id:
        # Tentar URL alternativa primeiro
        url_alternativa = verificar_url_alternativa(video_id)
        if url_alternativa:
            url = url_alternativa
            logger.info("🔄 Usando URL alternativa para contornar bloqueio")
    
    for tentativa in range(tentativas):
        try:
            logger.info(f"🔄 TENTATIVA {tentativa + 1}/{tentativas} - Estratégia {tentativa + 1}")
            
            # Delay estratégico progressivo
            if tentativa > 0:
                wait_time = tentativa * 5 + random.randint(2, 8)
                logger.info(f"⏳ Delay estratégico de {wait_time}s...")
                time.sleep(wait_time)
            
            ydl_opts = obter_configuracao_extrema(tentativa)
            ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'temp_{id_processo}_v{tentativa}.%(ext)s')
            
            # Estratégia especial para tentativas finais
            if tentativa >= 4:
                ydl_opts['format'] = 'worstaudio/worst'
                ydl_opts['ignoreerrors'] = True
                ydl_opts['no_check_certificate'] = True
            
            logger.info(f"🎯 Aplicando estratégia anti-bloqueio {tentativa + 1}...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_completo = ydl.extract_info(url, download=True)
            
            # Verificar resultado do download
            for arquivo in os.listdir(TEMP_DIR):
                if f'temp_{id_processo}_v{tentativa}' in arquivo:
                    arquivo_path = os.path.join(TEMP_DIR, arquivo)
                    if os.path.exists(arquivo_path) and os.path.getsize(arquivo_path) > 50000:  # Mínimo 50KB
                        tamanho = os.path.getsize(arquivo_path) / (1024 * 1024)
                        logger.info(f"🎉 TENTATIVA {tentativa + 1} BEM-SUCEDIDA!")
                        logger.info(f"📦 Arquivo: {tamanho:.2f} MB")
                        return arquivo_path, info_completo.get('title', 'Áudio')
                    else:
                        logger.warning("📁 Arquivo muito pequeno, tentando próxima estratégia...")
                        try:
                            os.remove(arquivo_path)
                        except:
                            pass
                        continue
                        
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"⚠️  Tentativa {tentativa + 1} falhou: {error_msg[:100]}...")
            
            # Estratégias específicas para erros conhecidos
            if "Sign in to confirm you're not a bot" in error_msg:
                logger.info("🎯 BLOQUEIO DETECTADO! Aplicando contramedidas...")
                time.sleep(15)  # Delay maior para bloqueios
            elif "HTTP Error 429" in error_msg:
                logger.info("🔁 Rate limit detectado, aumentando delay...")
                time.sleep(30)
            continue
    
    # SE CHEGOU AQUI, TODAS AS ESTRATÉGIAS FALHARAM
    raise Exception(
        "🚫 BLOQUEIO TOTAL DO YOUTUBE\n\n"
        "O YouTube está bloqueando todas as tentativas. Isso é temporário.\n"
        "Soluções:\n"
        "• Aguarde 1-2 horas e tente novamente\n"
        "• Use outro vídeo para teste\n"
        "• O bloqueio é por IP e geralmente dura algumas horas\n"
        "• Tente vídeos menos populares ou mais antigos"
    )

def cortar_audio_preciso(arquivo_entrada, arquivo_saida, inicio_segundos, fim_segundos):
    """Corte temporal preciso com FFmpeg"""
    try:
        duracao = fim_segundos - inicio_segundos
        logger.info(f"✂️  Cortando áudio: {inicio_segundos}s → {fim_segundos}s ({duracao}s)")
        
        # PRIMEIRA TENTATIVA: Corte rápido sem recompressão
        comando = [
            'ffmpeg', '-i', arquivo_entrada,
            '-ss', str(inicio_segundos), '-to', str(fim_segundos),
            '-c', 'copy', '-y', '-hide_banner', '-loglevel', 'error',
            arquivo_saida
        ]
        
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=120)
        
        if resultado.returncode == 0 and os.path.exists(arquivo_saida):
            tamanho = os.path.getsize(arquivo_saida) / (1024 * 1024)
            logger.info(f"✅ Corte rápido concluído: {tamanho:.2f} MB")
            return True
        
        # SEGUNDA TENTATIVA: Com recompressão MP3
        comando = [
            'ffmpeg', '-i', arquivo_entrada,
            '-ss', str(inicio_segundos), '-to', str(fim_segundos),
            '-c:a', 'libmp3lame', '-b:a', '192k', 
            '-af', 'volume=1.0', '-y',
            '-hide_banner', '-loglevel', 'error',
            arquivo_saida
        ]
        
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)
        
        if resultado.returncode == 0 and os.path.exists(arquivo_saida):
            tamanho = os.path.getsize(arquivo_saida) / (1024 * 1024)
            logger.info(f"✅ Corte com recompressão concluído: {tamanho:.2f} MB")
            return True
            
        raise Exception(f"FFmpeg falhou após 2 tentativas")
        
    except subprocess.TimeoutExpired:
        raise Exception("Timeout no corte de áudio")
    except Exception as e:
        raise Exception(f"Erro no corte: {e}")

def processar_audio_extremo(url, inicio_segundos, fim_segundos, id_processo, nome_arquivo=None):
    """Processamento com todas as estratégias anti-bloqueio"""
    arquivo_temp = None
    try:
        logger.info(f"🎬 INICIANDO PROCESSAMENTO ULTRA-RESISTENTE: {id_processo}")
        logger.info(f"🔗 URL: {url}")
        logger.info(f"⏰ Corte: {inicio_segundos}s a {fim_segundos}s")
        
        # Validações
        if fim_segundos <= inicio_segundos:
            raise Exception("Tempo final deve ser maior que o inicial")
        
        if fim_segundos - inicio_segundos > 3600:  # 1 hora máximo
            raise Exception("Corte máximo de 1 hora")
        
        # 1. DOWNLOAD COM ESTRATÉGIAS EXTREMAS
        logger.info("📥 INICIANDO SISTEMA ANTI-BLOQUEIO...")
        arquivo_temp, titulo = baixar_com_estrategia_extrema(url, id_processo, tentativas=6)
        
        # 2. PREPARAR ARQUIVO FINAL
        if nome_arquivo and nome_arquivo.strip():
            nome_base = sanitizar_nome_arquivo(nome_arquivo)
            nome_final = f"{nome_base}.mp3"
        else:
            nome_base = sanitizar_nome_arquivo(titulo) or f"audio_{id_processo}"
            nome_final = f"{nome_base}.mp3"
        
        arquivo_final = os.path.join(AUDIO_FILES_DIR, nome_final)
        
        # 3. CORTE PRECISO
        logger.info("🔧 APLICANDO CORTE TEMPORAL...")
        cortar_audio_preciso(arquivo_temp, arquivo_final, inicio_segundos, fim_segundos)
        
        # 4. VERIFICAÇÃO FINAL
        if not os.path.exists(arquivo_final):
            raise Exception("Arquivo final não foi criado")
        
        tamanho_final = os.path.getsize(arquivo_final) / (1024 * 1024)
        duracao_corte = fim_segundos - inicio_segundos
        
        logger.info(f"🎉 SUCESSO TOTAL! Processamento {id_processo} concluído!")
        logger.info(f"📁 Arquivo: {nome_final}")
        logger.info(f"📏 Tamanho: {tamanho_final:.2f} MB")
        logger.info(f"⏱️  Duração: {duracao_corte}s")
        
        return {
            'sucesso': True,
            'arquivo': nome_final,
            'tamanho_mb': round(tamanho_final, 2),
            'duracao_corte': duracao_corte
        }
        
    except Exception as e:
        logger.error(f"❌ FALHA NO PROCESSAMENTO {id_processo}: {e}")
        return {'sucesso': False, 'erro': str(e)}
    finally:
        # LIMPEZA COMPLETA
        if arquivo_temp and os.path.exists(arquivo_temp):
            try:
                os.remove(arquivo_temp)
                logger.info("🧹 Arquivo temporário removido")
            except:
                pass
        
        # Limpeza de todos os arquivos temporários
        for arquivo in os.listdir(TEMP_DIR):
            if f"temp_{id_processo}" in arquivo:
                try:
                    os.remove(os.path.join(TEMP_DIR, arquivo))
                except:
                    pass

# ROTAS DA API
@app.route('/')
def home():
    return jsonify({
        'mensagem': 'YouTube Audio API - Solução Definitiva',
        'status': '🟢 Online',
        'versao': '4.0',
        'recursos': [
            '6 Estratégias Anti-Bloqueio',
            'URLs Alternativas',
            'Sistema Stealth',
            'Corte Preciso'
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
            return jsonify({'erro': 'URL do YouTube é obrigatória'}), 400
        
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return jsonify({'erro': 'URL do YouTube inválida'}), 400
        
        if fim <= inicio:
            return jsonify({'erro': 'Tempo final deve ser maior que o inicial'}), 400
        
        id_processo = str(uuid.uuid4())[:8]
        
        logger.info(f"📋 NOVO PROCESSO ULTRA-RESISTENTE: {id_processo}")
        
        thread = threading.Thread(
            target=executar_processamento_extremo,
            args=(url, inicio, fim, id_processo, nome_arquivo)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'sucesso': True,
            'id_processo': id_processo,
            'mensagem': 'Processamento iniciado com sistema anti-bloqueio',
            'detalhes': {
                'estrategias': 6,
                'inicio_segundos': inicio,
                'fim_segundos': fim,
                'duracao_corte': fim - inicio
            }
        })
        
    except Exception as e:
        logger.error(f"💥 Erro em /api/processar: {e}")
        return jsonify({'erro': str(e)}), 500

def executar_processamento_extremo(url, inicio, fim, id_processo, nome_arquivo):
    """Wrapper para execução em thread"""
    try:
        resultado = processar_audio_extremo(url, inicio, fim, id_processo, nome_arquivo)
        if resultado['sucesso']:
            logger.info(f"🎉 {id_processo} - SUCESSO COMPLETO!")
        else:
            logger.error(f"❌ {id_processo} - FALHA: {resultado['erro']}")
    except Exception as e:
        logger.error(f"💥 {id_processo} - ERRO CRÍTICO: {e}")

@app.route('/api/status/<id_processo>')
def verificar_status(id_processo):
    try:
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
        
        for arquivo in os.listdir(TEMP_DIR):
            if f"temp_{id_processo}" in arquivo:
                return jsonify({
                    'sucesso': True,
                    'status': 'processando',
                    'mensagem': 'Sistema anti-bloqueio em ação...'
                })
        
        return jsonify({
            'sucesso': True,
            'status': 'processando', 
            'mensagem': 'Iniciando processamento ultra-resistente...'
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*70)
    print("🚀 YOUTUBE AUDIO API - SOLUÇÃO DEFINITIVA CONTRA BLOQUEIOS")
    print("="*70)
    print("🛡️  6 Estratégias Anti-Bloqueio")
    print("🌐 URLs Alternativas (Invidious/YewTu)")
    print("🎯 Sistema Stealth Avançado")
    print("⚡ 20 Retries Automáticos")
    print("="*70)
    print(f"🌐 Servidor iniciando na porta {port}...")
    print("="*70)

    app.run(host='0.0.0.0', port=port, debug=False)
