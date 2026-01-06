import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import re
import signal
import sys

class HangmanClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Wisielec - Klient (Wersja Finalna)")
        self.root.geometry("1100x750")
        
        self.client_socket = None
        self.connected = False
        self.current_errors = -1
        self.game_visible = False
        self.nick_set = False 

        # Obsługa zamknięcia okna "X"
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # GŁÓWNY UKŁAD
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Lewa strona
        self.left_frame = tk.Frame(self.main_frame)
        self.left_frame.pack(side='left', fill='both', expand=True)

        # Prawa strona
        self.right_frame = tk.Frame(self.main_frame, bg="white", bd=2, relief="sunken")

        # 1. POŁĄCZENIE
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

        # 2, LOBBY
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

        # 3. POKÓJ
        self.room_frame = tk.LabelFrame(self.left_frame, text="Opcje Pokoju", padx=5, pady=5)
        self.room_frame.pack(pady=5, fill='x')

        self.btn_leave = tk.Button(self.room_frame, text="Opuść Pokój", command=self.action_leave, width=20, bg="#FF9800")
        self.btn_leave.pack(side='left', padx=5)

        # Startowy reset
        self.disable_all_buttons()

        # 4. LOGI
        self.log_area = scrolledtext.ScrolledText(self.left_frame, state='disabled', height=20, font=("Consolas", 10))
        self.log_area.pack(pady=5, fill='both', expand=True)

        # 5. INPUT
        send_frame = tk.Frame(self.left_frame)
        send_frame.pack(pady=5, fill='x')

        tk.Label(send_frame, text="Wpisz:").pack(side='left')
        self.entry_msg = tk.Entry(send_frame, font=("Arial", 12))
        self.entry_msg.pack(side='left', fill='x', expand=True, padx=5)
        self.entry_msg.bind("<Return>", lambda event: self.send_message())

        self.btn_send = tk.Button(send_frame, text="Wyślij", command=self.send_message, bg="#2196F3", fg="white", width=10)
        self.btn_send.pack(side='left')

        # PRAWY PANEL
        tk.Label(self.right_frame, text="TWÓJ WISIELEC", bg="white", font=("Arial", 12, "bold")).pack(pady=10)
        self.canvas = tk.Canvas(self.right_frame, width=350, height=450, bg="white", highlightthickness=0)
        self.canvas.pack(padx=20, pady=20)
        self.draw_hangman(0)

    # ZARZĄDZANIE STANEM PRZYCISKÓW

    def disable_all_buttons(self):
        s = "disabled"
        self.btn_nick.config(state=s)
        self.btn_list.config(state=s)
        self.btn_create.config(state=s)
        self.btn_join.config(state=s)
        self.btn_leave.config(state=s)

    def set_ui_connected_no_nick(self):
        self.disable_all_buttons()
        self.btn_nick.config(state="normal", bg="#4CAF50", fg="white")

    def set_ui_lobby(self):
        """Tryb Lobby - można tworzyć pokoje, ale nie można wyjść"""
        self.nick_set = True
        self.btn_nick.config(state="disabled", bg="#dddddd", fg="black")
        
        self.btn_list.config(state="normal")
        self.btn_create.config(state="normal")
        self.btn_join.config(state="normal")
        
        self.btn_leave.config(state="disabled")

    def set_ui_room(self):
        """Tryb Pokoju - blokujemy wszystko oprócz wyjścia"""
        # Blokada Lobby
        self.btn_nick.config(state="disabled")
        self.btn_create.config(state="disabled")
        self.btn_join.config(state="disabled")
        self.btn_list.config(state="disabled")
        
        # Odblokowanie Wyjścia
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

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        self.parse_server_message(message)

    # KLUCZOWA LOGIKA ANALIZY KOMUNIKATÓW

    def parse_server_message(self, message):
        # 1. Start
        if "Podaj swój nick" in message or "Witaj na serwerze" in message:
            self.set_ui_connected_no_nick()

        # 2. Lobby
        if "OK Witaj" in message:
            self.set_ui_lobby()
            self.log("[INFO] Jesteś w Lobby.")

        # 3. Wejście do pokoju
        if "Dołączono do" in message or "Utworzono pokój" in message or "Oczekiwanie na" in message:
            self.set_ui_room()

        # 4. Fail-safe (Hasło = Pokój)
        if "HASŁO:" in message:
            # Upewniamy się, że jesteśmy w trybie pokoju
            if self.btn_leave['state'] == 'disabled':
                self.set_ui_room()
            
            if not self.game_visible:
                self.clear_logs()
                self.toggle_game_panel(True)

        # 5. Wyjście z pokoju
        if "Wyszedłeś z pokoju" in message:
            self.set_ui_lobby()
            self.toggle_game_panel(False)
            self.current_errors = 0
            self.clear_logs()
            self.log("--- LOBBY ---")
            self.draw_hangman(0)

        # 6. Rysowanie
        match = re.search(r">\s+.*?Wisielec:\s+(\d+)/7", message)
        if match:
            errors = int(match.group(1))
            if errors != self.current_errors:
                self.current_errors = errors
                self.draw_hangman(errors)
        
        if "został powieszony" in message or "PRZEGRANA" in message or "Wszyscy gracze wyeliminowani" in message:
            self.draw_hangman(7)
            self.current_errors = 7
        
        # 7. Nowa runda
        if "ROZPOCZYNAMY NOWĄ RUNDĘ" in message:
            self.clear_logs()
            self.log("[GRA] Nowa Runda!")
            self.toggle_game_panel(True)
            self.draw_hangman(0)
            self.current_errors = 0

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
            self.log(f"[BŁĄD] {e}")
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

    def action_leave(self):
        self.send_cmd("LEAVE")

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
            
            self.log(f"[SYSTEM] Połączono z {ip}:{port}")
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
        self.log("[SYSTEM] Rozłączono.")
        self.nick_set = False

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