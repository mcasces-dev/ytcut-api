import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import uuid
import threading
import subprocess
import re

print("🚀 INICIANDO YOUTUBE AUDIO API - CORTE PRECISO")

# Configuração do Flask
app = Flask(__name__)
CORS(app)

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Diretórios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILES_DIR = os.path.join(BASE_DIR, 'audio_files')
TEMP_DIR = os.path.join(BASE_DIR, 'temp_downloads')

# Criar diretórios se não existirem
os.makedirs(AUDIO_FILES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

print(f"📁 Diretório de áudios: {AUDIO_FILES_DIR}")
print(f"📁 Diretório temporário: {TEMP_DIR}")


def sanitizar_nome_arquivo(nome):
    """Remove caracteres inválidos do nome do arquivo"""
    if not nome:
        return None
    nome = re.sub(r'[^\w\s\-_]', '', nome)
    nome = nome.replace(' ', '_')
    return nome[:50]


def obter_info_video(url):
    """Obtém informações detalhadas do vídeo"""
    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'titulo': info.get('title', 'Título não disponível'),
                'duracao': info.get('duration', 0),
                'autor': info.get('uploader', 'Autor não disponível'),
                'thumbnail': info.get('thumbnail', ''),
                'visualizacoes': info.get('view_count', 0)
            }
    except Exception as e:
        logger.error(f"Erro ao obter info do vídeo: {e}")
        return None


def baixar_audio_completo(url, id_processo):
    """Baixa o áudio completo em alta qualidade"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(TEMP_DIR, f'temp_{id_processo}.%(ext)s'),
            'extractaudio': True,
            'audioformat': 'best',
            'quiet': False,
            'no_warnings': False,
        }

        logger.info(f"📥 Iniciando download do áudio completo...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Encontrar arquivo baixado
        for arquivo in os.listdir(TEMP_DIR):
            if arquivo.startswith(f'temp_{id_processo}'):
                arquivo_path = os.path.join(TEMP_DIR, arquivo)
                tamanho = os.path.getsize(arquivo_path) / (1024 * 1024)  # MB
                logger.info(f"✅ Download concluído: {arquivo} ({tamanho:.2f} MB)")
                return arquivo_path, info.get('title', 'Áudio')

        raise Exception("Arquivo baixado não encontrado")

    except Exception as e:
        raise Exception(f"Erro no download: {str(e)}")


def cortar_audio_preciso(arquivo_entrada, arquivo_saida, inicio_segundos, fim_segundos):
    """Corta o áudio com precisão usando FFmpeg"""
    try:
        duracao = fim_segundos - inicio_segundos

        # Verificar se o arquivo de entrada existe
        if not os.path.exists(arquivo_entrada):
            raise Exception(f"Arquivo de entrada não encontrado: {arquivo_entrada}")

        logger.info(f"✂️  Cortando áudio: {inicio_segundos}s → {fim_segundos}s (duração: {duracao}s)")

        # PRIMEIRA TENTATIVA: Corte rápido sem recompressão
        comando = [
            'ffmpeg',
            '-i', arquivo_entrada,
            '-ss', str(inicio_segundos),  # Ponto de início
            '-t', str(duracao),  # Duração do corte
            '-c', 'copy',  # Copiar stream sem recompressão (rápido)
            '-y',  # Sobrescrever arquivo de saída
            '-avoid_negative_ts', 'make_zero',  # Corrigir timestamps negativos
            '-hide_banner',  # Ocultar banner do FFmpeg
            '-loglevel', 'warning',  # Apenas logs importantes
            arquivo_saida
        ]

        logger.info(f"🔧 Executando FFmpeg (corte rápido)...")
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=120)

        if resultado.returncode == 0 and os.path.exists(arquivo_saida):
            tamanho = os.path.getsize(arquivo_saida) / (1024 * 1024)
            logger.info(f"✅ Corte rápido concluído: {tamanho:.2f} MB")
            return True

        # SEGUNDA TENTATIVA: Corte com recompressão e fade
        logger.info("🔄 Tentando corte com recompressão...")
        comando = [
            'ffmpeg',
            '-i', arquivo_entrada,
            '-ss', str(inicio_segundos),
            '-t', str(duracao),
            '-c:a', 'libmp3lame',  # Codec MP3
            '-b:a', '192k',  # Bitrate 192kbps
            '-af', f'afade=t=in:st=0:d=0.5,afade=t=out:st={duracao - 0.5}:d=0.5',  # Fade in/out
            '-y',
            '-hide_banner',
            '-loglevel', 'warning',
            arquivo_saida
        ]

        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)

        if resultado.returncode != 0:
            raise Exception(f"FFmpeg falhou: {resultado.stderr}")

        if os.path.exists(arquivo_saida):
            tamanho = os.path.getsize(arquivo_saida) / (1024 * 1024)
            logger.info(f"✅ Corte com recompressão concluído: {tamanho:.2f} MB")
            return True
        else:
            raise Exception("Arquivo de saída não foi criado")

    except subprocess.TimeoutExpired:
        raise Exception("Tempo limite excedido no corte de áudio")
    except Exception as e:
        raise Exception(f"Erro no corte: {str(e)}")


def processar_audio_completo(url, inicio_segundos, fim_segundos, id_processo, nome_arquivo=None):
    """Processamento completo com corte preciso"""
    arquivo_temp = None
    try:
        # 1. VALIDAR PARÂMETROS
        if fim_segundos <= inicio_segundos:
            raise Exception("O tempo final deve ser maior que o inicial")

        if fim_segundos - inicio_segundos > 7200:  # Máximo 2 horas
            raise Exception("O corte não pode ter mais de 2 horas")

        # 2. OBTER INFORMAÇÕES DO VÍDEO
        info_video = obter_info_video(url)
        if not info_video:
            raise Exception("Não foi possível obter informações do vídeo")

        duracao_video = info_video['duracao']
        if inicio_segundos >= duracao_video:
            raise Exception(f"O tempo inicial ({inicio_segundos}s) é maior que a duração do vídeo ({duracao_video}s)")

        if fim_segundos > duracao_video:
            logger.warning(f"⚠️  Ajustando tempo final de {fim_segundos}s para {duracao_video}s")
            fim_segundos = duracao_video

        # 3. BAIXAR ÁUDIO COMPLETO
        arquivo_temp, titulo_video = baixar_audio_completo(url, id_processo)

        # 4. PREPARAR NOME DO ARQUIVO FINAL
        if nome_arquivo and nome_arquivo.strip():
            nome_base = sanitizar_nome_arquivo(nome_arquivo)
            nome_final = f"{nome_base}.mp3"
        else:
            # Usar título do vídeo se não houver nome personalizado
            nome_base = sanitizar_nome_arquivo(titulo_video) or f"audio_{id_processo}"
            nome_final = f"{nome_base}.mp3"

        arquivo_final = os.path.join(AUDIO_FILES_DIR, nome_final)

        # 5. EXECUTAR CORTE PRECISO
        cortar_audio_preciso(arquivo_temp, arquivo_final, inicio_segundos, fim_segundos)

        # 6. VERIFICAR RESULTADO
        if not os.path.exists(arquivo_final):
            raise Exception("Arquivo final não foi criado")

        tamanho_final = os.path.getsize(arquivo_final) / (1024 * 1024)
        logger.info(f"🎉 Processamento concluído: {nome_final} ({tamanho_final:.2f} MB)")

        return {
            'sucesso': True,
            'arquivo': nome_final,
            'tamanho_mb': round(tamanho_final, 2),
            'duracao_corte': fim_segundos - inicio_segundos
        }

    except Exception as e:
        logger.error(f"❌ Erro no processamento: {str(e)}")
        return {
            'sucesso': False,
            'erro': str(e)
        }
    finally:
        # LIMPEZA: Remover arquivo temporário
        if arquivo_temp and os.path.exists(arquivo_temp):
            try:
                os.remove(arquivo_temp)
                logger.info("🧹 Arquivo temporário removido")
            except Exception as e:
                logger.warning(f"⚠️  Não foi possível remover arquivo temporário: {e}")


# ===== ROTAS DA API =====
@app.route('/')
def home():
    return jsonify({
        'mensagem': 'YouTube Audio API - Corte Preciso',
        'status': '🟢 Online',
        'versao': '2.0',
        'recursos': [
            'Corte preciso com FFmpeg',
            'Fade in/out automático',
            'Validação de tempos',
            'Nomes de arquivo personalizados'
        ]
    })


@app.route('/api/info', methods=['POST'])
def obter_informacoes():
    """Obtém informações detalhadas do vídeo"""
    try:
        dados = request.get_json()
        url = dados.get('url', '').strip()

        if not url:
            return jsonify({'erro': 'URL do YouTube é obrigatória'}), 400

        if 'youtube.com' not in url and 'youtu.be' not in url:
            return jsonify({'erro': 'URL do YouTube inválida'}), 400

        info = obter_info_video(url)
        if not info:
            return jsonify({'erro': 'Não foi possível obter informações do vídeo'}), 400

        return jsonify({
            'sucesso': True,
            'titulo': info['titulo'],
            'duracao': info['duracao'],
            'duracao_formatada': f"{info['duracao'] // 60}:{info['duracao'] % 60:02d}",
            'autor': info['autor'],
            'thumbnail': info['thumbnail']
        })

    except Exception as e:
        logger.error(f"Erro em /api/info: {str(e)}")
        return jsonify({'erro': 'Erro interno do servidor'}), 500


@app.route('/api/processar', methods=['POST'])
def processar_audio():
    """Inicia o processamento do áudio com corte preciso"""
    try:
        dados = request.get_json()
        url = dados.get('url', '').strip()
        inicio = int(dados.get('inicio', 0))
        fim = int(dados.get('fim', 30))
        nome_arquivo = dados.get('nome_arquivo', '').strip()

        # Validações
        if not url:
            return jsonify({'erro': 'URL do YouTube é obrigatória'}), 400

        if 'youtube.com' not in url and 'youtu.be' not in url:
            return jsonify({'erro': 'URL do YouTube inválida'}), 400

        if fim <= inicio:
            return jsonify({'erro': 'O tempo final deve ser maior que o inicial'}), 400

        if fim - inicio > 7200:  # 2 horas
            return jsonify({'erro': 'O corte não pode ter mais de 2 horas'}), 400

        # Gerar ID do processo
        id_processo = str(uuid.uuid4())[:8]
        logger.info(f"📋 Novo processo: {id_processo} - {inicio}s a {fim}s")

        # Executar em thread
        thread = threading.Thread(
            target=executar_processamento,
            args=(url, inicio, fim, id_processo, nome_arquivo)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'sucesso': True,
            'id_processo': id_processo,
            'mensagem': 'Processamento iniciado com corte preciso',
            'detalhes': {
                'inicio_segundos': inicio,
                'fim_segundos': fim,
                'duracao_corte': fim - inicio
            }
        })

    except Exception as e:
        logger.error(f"Erro em /api/processar: {str(e)}")
        return jsonify({'erro': str(e)}), 500


def executar_processamento(url, inicio, fim, id_processo, nome_arquivo):
    """Wrapper para execução em thread"""
    try:
        resultado = processar_audio_completo(url, inicio, fim, id_processo, nome_arquivo)
        if resultado['sucesso']:
            logger.info(f"🎉 Processo {id_processo} concluído com sucesso")
        else:
            logger.error(f"❌ Processo {id_processo} falhou: {resultado['erro']}")
    except Exception as e:
        logger.error(f"💥 Erro crítico no processo {id_processo}: {str(e)}")


@app.route('/api/status/<id_processo>')
def verificar_status(id_processo):
    """Verifica o status do processamento"""
    try:
        # Procurar arquivo pelo ID do processo
        for arquivo in os.listdir(AUDIO_FILES_DIR):
            if f"_{id_processo}.mp3" in arquivo or arquivo.endswith(f"{id_processo}.mp3"):
                caminho_arquivo = os.path.join(AUDIO_FILES_DIR, arquivo)
                tamanho = os.path.getsize(caminho_arquivo) / (1024 * 1024)

                return jsonify({
                    'sucesso': True,
                    'status': 'concluido',
                    'arquivo': arquivo,
                    'tamanho_mb': round(tamanho, 2),
                    'download_url': f'/api/download/{id_processo}'
                })

        # Se não encontrou, verificar se há arquivo temporário (ainda processando)
        for arquivo in os.listdir(TEMP_DIR):
            if f"temp_{id_processo}" in arquivo:
                return jsonify({
                    'sucesso': True,
                    'status': 'processando',
                    'mensagem': 'Download e corte em andamento...'
                })

        return jsonify({
            'sucesso': True,
            'status': 'processando',
            'mensagem': 'Processamento iniciado...'
        })

    except Exception as e:
        logger.error(f"Erro em /api/status: {str(e)}")
        return jsonify({'erro': str(e)}), 500


@app.route('/api/download/<id_processo>')
def download_audio(id_processo):
    """Faz download do áudio processado"""
    try:
        # Procurar arquivo pelo ID
        arquivo_encontrado = None
        for arquivo in os.listdir(AUDIO_FILES_DIR):
            if f"_{id_processo}.mp3" in arquivo or arquivo.endswith(f"{id_processo}.mp3"):
                arquivo_encontrado = arquivo
                break

        if not arquivo_encontrado:
            return jsonify({'erro': 'Arquivo não encontrado'}), 404

        caminho_arquivo = os.path.join(AUDIO_FILES_DIR, arquivo_encontrado)

        return send_file(
            caminho_arquivo,
            as_attachment=True,
            download_name=arquivo_encontrado
        )

    except Exception as e:
        logger.error(f"Erro em /api/download: {str(e)}")
        return jsonify({'erro': str(e)}), 500


@app.route('/api/limpar', methods=['POST'])
def limpar_arquivos():
    """Limpa arquivos temporários (para administração)"""
    try:
        import shutil
        for pasta in [TEMP_DIR, AUDIO_FILES_DIR]:
            for arquivo in os.listdir(pasta):
                caminho_arquivo = os.path.join(pasta, arquivo)
                try:
                    os.remove(caminho_arquivo)
                except:
                    pass
        return jsonify({'sucesso': True, 'mensagem': 'Arquivos limpos'})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ===== INICIALIZAÇÃO =====
if __name__ == '__main__':
    # Obter porta das variáveis de ambiente (Render usa PORT)
    port = int(os.environ.get('PORT', 5000))

    print("\n" + "=" * 60)
    print("🎵 YOUTUBE AUDIO API - CORTE PRECISO")
    print("=" * 60)
    print("📊 Endpoints disponíveis:")
    print("   GET  /                 - Status da API")
    print("   POST /api/info         - Informações do vídeo")
    print("   POST /api/processar    - Processar áudio com corte preciso")
    print("   GET  /api/status/:id   - Verificar status")
    print("   GET  /api/download/:id - Download do áudio")
    print("   POST /api/limpar       - Limpar arquivos (admin)")
    print("=" * 60)
    print("🚀 Servidor iniciando na porta 5000...")
    print("💡 Dica: Use vídeos curtos para teste inicial")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=True)