from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse
import subprocess
import yt_dlp

def youtube_search(query, max_results=10):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'ignoreerrors': True,
    }
    output_lines = []
    try:
        search_target = f"ytsearch{max_results}:{query}"
        print(f"[Arama Yapiliyor] -> {query}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry and entry.get('id'):
                        title = entry.get('title', 'Video').replace("\n", " ").replace("|", "-")
                        video_id = entry.get('id')
                        output_lines.append(f"{title}|{video_id}")
    except Exception as e:
        print(f"[Arama Hata]: {e}")
    return "\n".join(output_lines)

def get_stream_url(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb']
            }
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get('url')
    except Exception as e:
        print(f"[Stream Hata]: {e}")
    return None

class SymTubeRelayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_url.query)
        
        # 1. KÜÇÜK RESİM SERVİSİ
        if parsed_url.path == '/thumb':
            video_id = params.get('v', [''])[0]
            if video_id:
                thumb_url = f"https://i.ytimg.com/vi/{video_id}/default.jpg"
                try:
                    req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        if resp.status == 200:
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.end_headers()
                            self.wfile.write(resp.read())
                            return
                except Exception:
                    pass
            self.send_response(404)
            self.end_headers()

        # 2. DAHİLİ OYNATICI İÇİN FFMPEG 3GP/AMR STREAM SERVİSİ
        elif parsed_url.path == '/play':
            video_id = params.get('v', [''])[0]
            if video_id:
                stream_url = get_stream_url(video_id)
                if stream_url:
                    print(f"[FFmpeg Transcode] 3GP / AMR-NB akisi baslatiliyor: {video_id}")
                    
                    # FFmpeg Komutu: J2ME / Sun WTK MMAPI uyumlu 3GP canlı akışı
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-y',
                        '-headers', 'User-Agent: Mozilla/5.0\r\n',
                        '-i', stream_url,
                        '-vf', 'scale=240:180:force_original_aspect_ratio=decrease,pad=240:180:(ow-iw)/2:(oh-ih)/2',
                        '-c:v', 'h263',
                        '-b:v', '128k',
                        '-r', '15',
                        '-c:a', 'amr_nb',                  # AAC yerine J2ME standardı AMR-NB
                        '-ar', '8000',                     # AMR için 8kHz
                        '-ac', '1',                        # Mono ses
                        '-movflags', 'frag_keyframe+empty_moov+default_base_moof', # Canlı Pipe akışı için şart
                        '-f', '3gp',
                        'pipe:1'
                    ]

                    proc = None
                    try:
                        proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'video/3gpp')
                        self.end_headers()
                        
                        while True:
                            chunk = proc.stdout.read(8192)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                        return
                    except FileNotFoundError:
                        print("\n[KRİTİK HATA] 'ffmpeg' komutu sistemde bulunamadi!")
                        print("Lutfen ffmpeg.exe dosyasini 'relay.py' ile ayni klasore kopyalayin.\n")
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                        print("[Bilgi] Emülatör/Telefon baglantiyi kapatti.")
                    except Exception as e:
                        print(f"[Transcode Hatasi]: {e}")
                    finally:
                        if proc and proc.poll() is None:
                            proc.kill()
                            proc.wait()
            
            self.send_response(500)
            self.end_headers()

        # 3. HARİCİ OYNATICI İÇİN HAM LINK
        elif parsed_url.path == '/stream':
            video_id = params.get('v', [''])[0]
            if video_id:
                stream_url = get_stream_url(video_id)
                if stream_url:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(stream_url.encode('utf-8'))
                    return
            self.send_response(500)
            self.end_headers()

        # 4. TREND VİDEOLAR SERVİSİ
        elif parsed_url.path == '/trending':
            results = youtube_search("gündem", 10)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(results.encode('utf-8'))

        # 5. ARAMA İSTEĞİ
        else:
            search_query = params.get('q', [''])[0]
            if not search_query: 
                search_query = "symbian"
            results = youtube_search(search_query, 10)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(results.encode('utf-8'))

if __name__ == '__main__':
    httpd = HTTPServer(('0.0.0.0', 8080), SymTubeRelayHandler)
    print("==========================================")
    print("SymTube FFmpeg Transcoder & Proxy Server Aktif (Port 8080)")
    print("==========================================")
    httpd.serve_forever()