import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import re
import signal
import sys
import time

class HangmanClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Wisielec - Klient (Wersja UI Premium)")
        self.root.geometry("1200x800")
        
        self.client_socket = None
        self.connected = False
        self.current_errors = -1
        self.game_visible = False
        self.nick_set = False 
        
        # Minutnik
        self.timer_running = False
        self.last_server_elapsed = 0.0
        self.last_sync_time = 0.0
        self.max_round_time = 120

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # UKŁAD 
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        self.left_frame = tk.Frame(self.main_frame)
        self.left_frame.pack(side='left', fill='both', expand=True)

        self.right_frame = tk.Frame(self.main_frame, bg="white", bd=2, relief="sunken")

        # LEWA STRONA: POŁĄCZENIE
        conn_frame = tk.LabelFrame(self.left_frame, text="Połączenie", padx=5, pady=5)
        conn_frame.pack(pady=5, fill='x')

        tk.Label(conn_frame, text="IP:").pack(side='left')
        self.entry_ip = tk.Entry(conn_frame, width=15)
        self.entry_ip.insert(0, "127.0.0.1")
        self.entry_ip.pack(side='left', padx=5)

        tk.Label(conn_frame, text="Port:").pack(side='left')
        self.entry_port = tk.Entry(conn_frame, width=6)
        self.entry_port.insert(0, "12345")
        self.entry_port.pack(side='left', padx=5)

        self.btn_connect = tk.Button(conn_frame, text="Połącz", command=self.connect_to_server, bg="#8BC34A", fg="white")
        self.btn_connect.pack(side='left', padx=10)

        self.btn_disconnect = tk.Button(conn_frame, text="Rozłącz", command=self.disconnect_from_server, bg="#F44336", fg="white", state="disabled")
        self.btn_disconnect.pack(side='left', padx=10)

        # LEWA STRONA: LOBBY
        self.ctrl_frame = tk.LabelFrame(self.left_frame, text="Lobby", padx=5, pady=5)
        self.ctrl_frame.pack(pady=5, fill='x')
        self.btn_nick = tk.Button(self.ctrl_frame, text="Ustaw Nick", command=self.action_nick, width=12)
        self.btn_nick.pack(side='left', padx=5)
        self.btn_list = tk.Button(self.ctrl_frame, text="Lista Pokoi", command=self.action_list, width=12)
        self.btn_list.pack(side='left', padx=5)
        self.btn_create = tk.Button(self.ctrl_frame, text="Stwórz Pokój", command=self.action_create, width=12)
        self.btn_create.pack(side='left', padx=5)
        self.btn_join = tk.Button(self.ctrl_frame, text="Dołącz", command=self.action_join, width=12)
        self.btn_join.pack(side='left', padx=5)

        # LEWA STRONA: POKÓJ 
        self.room_frame = tk.LabelFrame(self.left_frame, text="Opcje Pokoju", padx=5, pady=5)
        self.room_frame.pack(pady=5, fill='x')
        self.btn_leave = tk.Button(self.room_frame, text="Opuść Pokój", command=self.action_leave, width=20, bg="#FF9800")
        self.btn_leave.pack(side='left', padx=5)

        self.disable_all_buttons()

        # LEWA STRONA: LOGI (i tabela wyników)
        log_label = tk.Label(self.left_frame, text="TABELA WYNIKÓW / LOGI", anchor="w")
        log_label.pack(pady=(5,0), fill='x')
        
        self.log_area = scrolledtext.ScrolledText(self.left_frame, state='disabled', height=20, font=("Consolas", 10))
        self.log_area.pack(pady=5, fill='both', expand=True)

        # LEWA STRONA: INPUT
        send_frame = tk.Frame(self.left_frame)
        send_frame.pack(pady=5, fill='x')
        tk.Label(send_frame, text="Zgadnij literę:").pack(side='left')
        self.entry_msg = tk.Entry(send_frame, font=("Arial", 12))
        self.entry_msg.pack(side='left', fill='x', expand=True, padx=5)
        self.entry_msg.bind("<Return>", lambda event: self.send_message())
        self.btn_send = tk.Button(send_frame, text="Wyślij", command=self.send_message, bg="#2196F3", fg="white", width=10)
        self.btn_send.pack(side='left')

        # PRAWA STRONA: PANELE GRY
        
        # 1. Info (Runda i Czas)
        self.info_frame = tk.Frame(self.right_frame, bg="white")
        self.info_frame.pack(fill='x', padx=10, pady=10)

        self.lbl_round = tk.Label(self.info_frame, text="RUNDA: -", font=("Arial", 14, "bold"), bg="white", fg="#555")
        self.lbl_round.pack(side='left', padx=10)

        self.lbl_time = tk.Label(self.info_frame, text="CZAS: 0s", font=("Arial", 14, "bold"), bg="white", fg="#d32f2f")
        self.lbl_time.pack(side='right', padx=10)

        # 2. HASŁO
        self.word_frame = tk.Frame(self.right_frame, bg="#f0f0f0", bd=1, relief="solid")
        self.word_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(self.word_frame, text="HASŁO:", bg="#f0f0f0", font=("Arial", 10)).pack(pady=(5,0))
        self.lbl_word = tk.Label(self.word_frame, text="_ _ _ _ _", font=("Courier New", 24, "bold"), bg="#f0f0f0", fg="black")
        self.lbl_word.pack(pady=(0,10))

        # 3. WISIELEC
        tk.Label(self.right_frame, text="TWÓJ WISIELEC", bg="white", font=("Arial", 10)).pack(pady=(20, 5))
        self.canvas = tk.Canvas(self.right_frame, width=350, height=400, bg="white", highlightthickness=0)
        self.canvas.pack(padx=20, pady=10)
        self.draw_hangman(0)

        self.run_timer_loop()

    # ZEGAR
    def run_timer_loop(self):
        if self.timer_running and self.connected:
            now = time.time()
            time_since_sync = now - self.last_sync_time
            estimated_elapsed = self.last_server_elapsed + time_since_sync
            if estimated_elapsed > self.max_round_time:
                estimated_elapsed = self.max_round_time
            self.lbl_time.config(text=f"CZAS: {int(estimated_elapsed)}s / {self.max_round_time}s")
        self.root.after(100, self.run_timer_loop)

    def sync_timer(self, server_elapsed):
        self.last_server_elapsed = server_elapsed
        self.last_sync_time = time.time()
        self.timer_running = True
        self.lbl_time.config(text=f"CZAS: {int(server_elapsed)}s / {self.max_round_time}s")

    def stop_timer(self):
        self.timer_running = False
        self.lbl_time.config(text="CZAS: -")

    # STAN UI
    def disable_all_buttons(self):
        s = "disabled"
        for btn in [self.btn_nick, self.btn_list, self.btn_create, self.btn_join, self.btn_leave]:
            btn.config(state=s)

    def set_ui_connected_no_nick(self):
        self.disable_all_buttons()
        self.btn_nick.config(state="normal", bg="#4CAF50", fg="white")

    def set_ui_lobby(self):
        self.nick_set = True
        self.btn_nick.config(state="disabled", bg="#dddddd", fg="black")
        self.btn_list.config(state="normal")
        self.btn_create.config(state="normal")
        self.btn_join.config(state="normal")
        self.btn_leave.config(state="disabled")
        self.stop_timer()

    def set_ui_room(self):
        self.btn_nick.config(state="disabled")
        self.btn_create.config(state="disabled")
        self.btn_join.config(state="disabled")
        self.btn_list.config(state="disabled")
        self.btn_leave.config(state="normal")

    def toggle_game_panel(self, show):
        if show and not self.game_visible:
            self.right_frame.pack(side='right', fill='both', padx=(10, 0))
            self.game_visible = True
        elif not show and self.game_visible:
            self.right_frame.pack_forget()
            self.game_visible = False

    def clear_logs(self):
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', tk.END)
        self.log_area.config(state='disabled')

    def reset_info_labels(self):
        self.lbl_round.config(text="RUNDA: -")
        self.lbl_time.config(text="CZAS: 0s")
        self.lbl_word.config(text="_ _ _ _ _", fg="black")

    # GŁÓWNA LOGIKA LOGÓW I FILTRÓW

    def log(self, raw_message):
        """
        Ta funkcja:
        1. Analizuje surową wiadomość i aktualizuje UI (prawy panel).
        2. Czyści wiadomość z danych, które przenieśliśmy na prawy panel (Hasło, Czas).
        3. Wypisuje tylko to, co zostało (Tabela wyników, komunikaty).
        """
        
        # 1. Analiza stanu gry (decyduje o UI, przyciskach itp.)
        self.parse_game_logic(raw_message)

        # 2 ,Filtrowanie tekstu do wyświetlenia
        lines_to_show = []
        
        for line in raw_message.split('\n'):
            clean_line = line.strip()
            
            # FILTR (co nie pokazywać w LOGach)
            if clean_line.startswith("HASŁO:"):
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    self.lbl_word.config(text=parts[1].strip())
                continue
            
            if clean_line.startswith("Prawidłowe hasło:"):
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    # Pokazujemy rozwiązanie nad wisielcem
                    self.lbl_word.config(text=parts[1].strip(), fg="red")

            if clean_line.startswith("RUNDA:"):
                # Wyciągamy rundę do UI
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    self.lbl_round.config(text=f"RUNDA: {parts[1].strip()}")
                continue 

            if clean_line.startswith("CZAS:"):
                continue
            
            # OBSŁUGA NOWEJ RUNDY
            if "ROZPOCZYNAMY NOWĄ RUNDĘ" in clean_line:
                self.clear_logs()
                # Dodajemy linię do logów (start nowej rundy - informacja dla graczy)
                lines_to_show.append(clean_line)
                continue

            # Wszystko inne (Tabela wyników, chat, błędy) - dodajemy do logów
            lines_to_show.append(line)

        # 3. Wypisanie przefiltrowanego tekstu
        final_text = "\n".join(lines_to_show).strip()
        if final_text:
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, final_text + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')

    def parse_game_logic(self, message):
        """Tylko aktualizacja zmiennych i stanów, bez wypisywania tekstu"""
        
        # Podstawowe stany
        if "Podaj swój nick" in message or "Witaj na serwerze" in message:
            self.set_ui_connected_no_nick()
        if "OK Witaj" in message:
            self.set_ui_lobby()
        if "Dołączono do" in message or "Utworzono pokój" in message or "Oczekiwanie na" in message:
            self.set_ui_room()

        # Wyjście z pokoju
        if "Wyszedłeś z pokoju" in message:
            self.set_ui_lobby()
            self.toggle_game_panel(False)
            self.current_errors = 0
            self.clear_logs()
            self.reset_info_labels()
            self.stop_timer()


        # Fail-safe (Hasło = Pokój)
        if "HASŁO:" in message:
            if self.btn_leave['state'] == 'disabled':
                self.set_ui_room()
            if not self.game_visible:
                self.toggle_game_panel(True)
            if not self.timer_running:
                self.timer_running = True

        # Nowa runda
        if "ROZPOCZYNAMY NOWĄ RUNDĘ" in message:
            self.toggle_game_panel(True)
            self.draw_hangman(0)
            self.current_errors = 0
            self.sync_timer(0)
            self.lbl_word.config(fg="black")

        # Pozostał jeden gracz w pokoju - ukrywanie wisielca
        if "Za mało graczy, gra wstrzymana" in message:
            self.toggle_game_panel(False)
            self.stop_timer()
            self.current_errors=0
            self.reset_info_labels()

        # Synchronizacja Czasu (dla minutnika)
        match_time = re.search(r"CZAS:\s+(\d+)s", message)
        if match_time:
            self.sync_timer(float(match_time.group(1)))

        # Rysowanie Wisielca
        match = re.search(r">\s+.*?Wisielec:\s+(\d+)/7", message)
        if match:
            errors = int(match.group(1))
            if errors != self.current_errors:
                self.current_errors = errors
                self.draw_hangman(errors)

    def draw_hangman(self, step):
        self.canvas.delete("all")
        c = "black"
        w = 4
        ox, oy = 70, 70 
        
        self.canvas.create_line(20+ox, 280+oy, 120+ox, 280+oy, width=w, fill=c) 
        self.canvas.create_line(70+ox, 280+oy, 70+ox, 20+oy, width=w, fill=c)   
        self.canvas.create_line(70+ox, 20+oy, 180+ox, 20+oy, width=w, fill=c)   
        self.canvas.create_line(180+ox, 20+oy, 180+ox, 50+oy, width=w, fill=c)  

        if step >= 1: self.canvas.create_oval(160+ox, 50+oy, 200+ox, 90+oy, width=w, outline=c)
        if step >= 2: self.canvas.create_line(180+ox, 90+oy, 180+ox, 170+oy, width=w, fill=c)
        if step >= 3: self.canvas.create_line(180+ox, 110+oy, 150+ox, 140+oy, width=w, fill=c)
        if step >= 4: self.canvas.create_line(180+ox, 110+oy, 210+ox, 140+oy, width=w, fill=c)
        if step >= 5: self.canvas.create_line(180+ox, 170+oy, 150+ox, 220+oy, width=w, fill=c)
        if step >= 6: self.canvas.create_line(180+ox, 170+oy, 210+ox, 220+oy, width=w, fill=c)
        if step >= 7: 
            self.canvas.create_line(165+ox, 60+oy, 175+ox, 70+oy, width=3, fill="red")
            self.canvas.create_line(175+ox, 60+oy, 165+ox, 70+oy, width=3, fill="red")
            self.canvas.create_line(185+ox, 60+oy, 195+ox, 70+oy, width=3, fill="red")
            self.canvas.create_line(195+ox, 60+oy, 185+ox, 70+oy, width=3, fill="red")
            self.canvas.create_text(125+ox, 150+oy, text="PRZEGRANA", fill="red", font=("Arial", 28, "bold"), angle=30)

    # KOMUNIKACJA
    def send_cmd(self, cmd):
        if not self.connected: return
        try:
            self.client_socket.send((cmd + "\n").encode('utf-8'))
        except Exception as e:
            self.disconnect_from_server()

    def action_nick(self):
        nick = simpledialog.askstring("Nick", "Podaj swój nick:")
        if nick: self.send_cmd(f"NICK {nick}")
    def action_list(self): self.send_cmd("LIST")
    def action_create(self):
        room = simpledialog.askstring("Stwórz Pokój", "Podaj nazwę nowego pokoju:")
        if room: self.send_cmd(f"CREATE {room}")
    def action_join(self):
        room = simpledialog.askstring("Dołącz", "Podaj nazwę pokoju:")
        if room: self.send_cmd(f"JOIN {room}")
    def action_leave(self): self.send_cmd("LEAVE")

    def send_message(self):
        if not self.connected: return
        msg = self.entry_msg.get()
        if msg:
            self.send_cmd(msg)
            self.entry_msg.delete(0, tk.END)

    def connect_to_server(self):
        if self.connected: return
        ip = self.entry_ip.get()
        try:
            port = int(self.entry_port.get())
        except ValueError:
            messagebox.showerror("Błąd", "Port musi być liczbą!")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(3.0)
            self.client_socket.connect((ip, port))
            self.client_socket.settimeout(None)
            self.connected = True
            self.btn_connect.config(state="disabled", bg="#dddddd")
            self.btn_disconnect.config(state="normal", bg="#F44336")
            threading.Thread(target=self.receive_loop, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Błąd połączenia", f"Nie można połączyć:\n{e}")

    def disconnect_from_server(self):
        if not self.connected: return
        self.connected = False
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
            self.client_socket.close()
        except: pass
        self.client_socket = None
        self.btn_connect.config(state="normal", bg="#8BC34A")
        self.btn_disconnect.config(state="disabled", bg="#dddddd")
        self.disable_all_buttons()
        self.toggle_game_panel(False)
        self.clear_logs()
        self.reset_info_labels()
        self.nick_set = False
        self.stop_timer()

    def receive_loop(self):
        while self.connected:
            try:
                data = self.client_socket.recv(4096)
                if not data: break
                msg = data.decode('utf-8', errors='ignore')
                self.root.after(0, self.log, msg.strip())
            except: break
        if self.connected:
            self.root.after(0, self.disconnect_from_server)

    def on_closing(self):
        self.disconnect_from_server()
        self.root.destroy()
        sys.exit(0)

def signal_handler(sig, frame): sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    root = tk.Tk()
    client = HangmanClient(root)
    def check(): root.after(500, check)
    root.after(500, check)
    root.mainloop()