#!/usr/bin/env python3
"""
Klient gry Wisielec oparty na bibliotece Tkinter.
Obsługuje komunikację sieciową, logikę gry oraz interfejs graficzny.
"""

import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import re
import signal
import sys
import time


class HangmanClient:
    """
    Główna klasa klienta gry Wisielec.
    Zarządza połączeniem, stanem gry i wyświetlaniem elementów.
    """

    def __init__(self, master):
        """Inicjalizacja okna i zmiennych stanu."""
        self.root = master
        self.root.title(" Gra Wisielec")
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

        # Inicjalizacja komponentów UI
        self.entry_ip = None
        self.entry_port = None
        self.btn_connect = None
        self.btn_disconnect = None
        self.btn_nick = None
        self.btn_list = None
        self.btn_create = None
        self.btn_join = None
        self.btn_leave = None
        self.log_area = None
        self.entry_msg = None
        self.btn_send = None
        self.lbl_round = None
        self.lbl_time = None
        self.lbl_word = None
        self.canvas = None
        self.right_frame = None

        # Budowanie interfejsu
        self._setup_gui()

        # Uruchomienie pętli zegara
        self._run_timer_loop()

    def _setup_gui(self):
        """Konfiguracja głównego układu okna."""
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        left_frame = tk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        self.right_frame = tk.Frame(main_frame, bg="white", bd=2, relief="sunken")

        self._create_connection_panel(left_frame)
        self._create_lobby_panel(left_frame)
        self._create_room_panel(left_frame)
        self._create_log_area(left_frame)
        self._create_input_area(left_frame)
        self._create_game_panel()

    def _create_connection_panel(self, parent):
        """Tworzy panel połączenia (IP, Port)."""
        conn_frame = tk.LabelFrame(parent, text="Połączenie", padx=5, pady=5)
        conn_frame.pack(pady=5, fill='x')

        tk.Label(conn_frame, text="IP:").pack(side='left')
        self.entry_ip = tk.Entry(conn_frame, width=15)
        self.entry_ip.insert(0, "127.0.0.1")
        self.entry_ip.pack(side='left', padx=5)

        tk.Label(conn_frame, text="Port:").pack(side='left')
        self.entry_port = tk.Entry(conn_frame, width=6)
        self.entry_port.insert(0, "12345")
        self.entry_port.pack(side='left', padx=5)

        self.btn_connect = tk.Button(
            conn_frame, text="Połącz",
            command=self.connect_to_server,
            bg="#8BC34A", fg="white"
        )
        self.btn_connect.pack(side='left', padx=10)

        self.btn_disconnect = tk.Button(
            conn_frame, text="Rozłącz",
            command=self.disconnect_from_server,
            bg="#F44336", fg="white", state="disabled"
        )
        self.btn_disconnect.pack(side='left', padx=10)

    def _create_lobby_panel(self, parent):
        """Tworzy przyciski lobby."""
        ctrl_frame = tk.LabelFrame(parent, text="Lobby", padx=5, pady=5)
        ctrl_frame.pack(pady=5, fill='x')

        self.btn_nick = tk.Button(
            ctrl_frame, text="Ustaw Nick", command=self.action_nick, width=12
        )
        self.btn_nick.pack(side='left', padx=5)

        self.btn_list = tk.Button(
            ctrl_frame, text="Lista Pokoi", command=self.action_list, width=12
        )
        self.btn_list.pack(side='left', padx=5)

        self.btn_create = tk.Button(
            ctrl_frame, text="Stwórz Pokój", command=self.action_create, width=12
        )
        self.btn_create.pack(side='left', padx=5)

        self.btn_join = tk.Button(
            ctrl_frame, text="Dołącz", command=self.action_join, width=12
        )
        self.btn_join.pack(side='left', padx=5)

    def _create_room_panel(self, parent):
        """Tworzy przyciski sterowania pokojem."""
        room_frame = tk.LabelFrame(parent, text="Opcje Pokoju", padx=5, pady=5)
        room_frame.pack(pady=5, fill='x')
        self.btn_leave = tk.Button(
            room_frame, text="Opuść Pokój",
            command=self.action_leave, width=20, bg="#FF9800"
        )
        self.btn_leave.pack(side='left', padx=5)
        self._disable_all_buttons()

    def _create_log_area(self, parent):
        """Tworzy obszar logów/tabeli wyników."""
        log_label = tk.Label(parent, text="TABELA WYNIKÓW / LOGI", anchor="w")
        log_label.pack(pady=(5, 0), fill='x')

        self.log_area = scrolledtext.ScrolledText(
            parent, state='disabled', height=20, font=("Consolas", 10)
        )
        self.log_area.pack(pady=5, fill='both', expand=True)

    def _create_input_area(self, parent):
        """Tworzy pole do wpisywania wiadomości."""
        send_frame = tk.Frame(parent)
        send_frame.pack(pady=5, fill='x')
        tk.Label(send_frame, text="Zgadnij literę:").pack(side='left')

        self.entry_msg = tk.Entry(send_frame, font=("Arial", 12))
        self.entry_msg.pack(side='left', fill='x', expand=True, padx=5)
        self.entry_msg.bind("<Return>", lambda event: self.send_message())

        self.btn_send = tk.Button(
            send_frame, text="Wyślij",
            command=self.send_message,
            bg="#2196F3", fg="white", width=10
        )
        self.btn_send.pack(side='left')

    def _create_game_panel(self):
        """Tworzy prawy panel z grą (Wisielec,Runda, Czas, Hasło)."""
        # 1. Info (Runda i Czas)
        info_frame = tk.Frame(self.right_frame, bg="white")
        info_frame.pack(fill='x', padx=10, pady=10)

        self.lbl_round = tk.Label(
            info_frame, text="RUNDA: -",
            font=("Arial", 14, "bold"), bg="white", fg="#555"
        )
        self.lbl_round.pack(side='left', padx=10)

        self.lbl_time = tk.Label(
            info_frame, text="CZAS: 0s",
            font=("Arial", 14, "bold"), bg="white", fg="#d32f2f"
        )
        self.lbl_time.pack(side='right', padx=10)

        # 2. HASŁO
        word_frame = tk.Frame(self.right_frame, bg="#f0f0f0", bd=1, relief="solid")
        word_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(
            word_frame, text="HASŁO:", bg="#f0f0f0", font=("Arial", 10)
        ).pack(pady=(5, 0))

        self.lbl_word = tk.Label(
            word_frame, text="_ _ _ _ _",
            font=("Courier New", 24, "bold"), bg="#f0f0f0", fg="black"
        )
        self.lbl_word.pack(pady=(0, 10))

        # 3. WISIELEC
        tk.Label(
            self.right_frame, text="TWÓJ WISIELEC",
            bg="white", font=("Arial", 10)
        ).pack(pady=(20, 5))

        self.canvas = tk.Canvas(
            self.right_frame, width=350, height=400,
            bg="white", highlightthickness=0
        )
        self.canvas.pack(padx=20, pady=10)
        self._draw_hangman(0)

    # ZEGA

    def _run_timer_loop(self):
        """Pętla aktualizująca lokalny licznik czasu."""
        if self.timer_running and self.connected:
            now = time.time()
            time_since_sync = now - self.last_sync_time
            estimated_elapsed = self.last_server_elapsed + time_since_sync
            if estimated_elapsed > self.max_round_time:
                estimated_elapsed = self.max_round_time
            self.lbl_time.config(
                text=f"CZAS: {int(estimated_elapsed)}s / {self.max_round_time}s"
            )
        self.root.after(100, self._run_timer_loop)

    def _sync_timer(self, server_elapsed):
        """Synchronizuje lokalny zegar z czasem serwera."""
        self.last_server_elapsed = server_elapsed
        self.last_sync_time = time.time()
        self.timer_running = True
        self.lbl_time.config(
            text=f"CZAS: {int(server_elapsed)}s / {self.max_round_time}s"
        )

    def _stop_timer(self):
        """Zatrzymuje licznik czasu."""
        self.timer_running = False
        self.lbl_time.config(text="CZAS: -")

    # UI STATE

    def _disable_all_buttons(self):
        """Wyłącza wszystkie przyciski sterujące."""
        state = "disabled"
        buttons = [
            self.btn_nick, self.btn_list, self.btn_create,
            self.btn_join, self.btn_leave
        ]
        for btn in buttons:
            btn.config(state=state)

    def _set_ui_connected_no_nick(self):
        """Ustawia UI po połączeniu, ale przed podaniem nicku."""
        self._disable_all_buttons()
        self.btn_nick.config(state="normal", bg="#4CAF50", fg="white")

    def _set_ui_lobby(self):
        """Ustawia UI dla stanu Lobby."""
        self.nick_set = True
        self.btn_nick.config(state="disabled", bg="#dddddd", fg="black")
        self.btn_list.config(state="normal")
        self.btn_create.config(state="normal")
        self.btn_join.config(state="normal")
        self.btn_leave.config(state="disabled")
        self._stop_timer()

    def _set_ui_room(self):
        """Ustawia UI po wejściu do pokoju."""
        self.btn_nick.config(state="disabled")
        self.btn_create.config(state="disabled")
        self.btn_join.config(state="disabled")
        self.btn_list.config(state="disabled")
        self.btn_leave.config(state="normal")

    def _toggle_game_panel(self, show):
        """Pokazuje lub ukrywa prawy panel gry."""
        if show and not self.game_visible:
            self.right_frame.pack(side='right', fill='both', padx=(10, 0))
            self.game_visible = True
        elif not show and self.game_visible:
            self.right_frame.pack_forget()
            self.game_visible = False

    def _clear_logs(self):
        """Czyści okno logów."""
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', tk.END)
        self.log_area.config(state='disabled')

    def _reset_info_labels(self):
        """Resetuje etykiety informacyjne (runda, czas, hasło)."""
        self.lbl_round.config(text="RUNDA: -")
        self.lbl_time.config(text="CZAS: 0s")
        self.lbl_word.config(text="_ _ _ _ _", fg="black")

    # LOGIKA GRY

    def log(self, raw_message):
        """
        Filtruje i wyświetla wiadomości od serwera.
        Zarządza aktualizacją etykiet na podstawie treści wiadomości.
        """
        # 1. Analiza stanu gry
        self._parse_game_logic(raw_message)

        # 2, Filtrowanie tekstu do wyświetlenia
        lines_to_show = []

        for line in raw_message.split('\n'):
            clean_line = line.strip()

            if clean_line.startswith("HASŁO:"):
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    self.lbl_word.config(text=parts[1].strip())
                continue

            if clean_line.startswith("Prawidłowe hasło:"):
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    self.lbl_word.config(text=parts[1].strip(), fg="red")

            if clean_line.startswith("RUNDA:"):
                parts = clean_line.split(":", 1)
                if len(parts) > 1:
                    self.lbl_round.config(text=f"RUNDA: {parts[1].strip()}")
                continue

            if clean_line.startswith("CZAS:"):
                continue

            if "ROZPOCZYNAMY NOWĄ RUNDĘ" in clean_line:
                self._clear_logs()
                lines_to_show.append(clean_line)
                continue

            lines_to_show.append(line)

        # 3. Wypisanie
        final_text = "\n".join(lines_to_show).strip()
        if final_text:
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, final_text + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')

    def _parse_game_logic(self, message):
        """Aktualizuje wewnętrzny stan gry na podstawie wiadomości."""
        # Podstawowe stany
        if "Podaj swój nick" in message or "Witaj na serwerze" in message:
            self._set_ui_connected_no_nick()
        if "OK Witaj" in message:
            self._set_ui_lobby()
        if any(x in message for x in ["Dołączono do", "Utworzono pokój", "Oczekiwanie na"]):
            self._set_ui_room()

        # Wyjście z pokoju
        if "Wyszedłeś z pokoju" in message:
            self._set_ui_lobby()
            self._toggle_game_panel(False)
            self.current_errors = 0
            self._clear_logs()
            self._reset_info_labels()
            self._stop_timer()

        # Fail-safe (Hasło = Jesteśmy w pokoju)
        if "HASŁO:" in message:
            if self.btn_leave['state'] == 'disabled':
                self._set_ui_room()
            if not self.game_visible:
                self._toggle_game_panel(True)
            if not self.timer_running:
                self.timer_running = True

        # Nowa runda
        if "ROZPOCZYNAMY NOWĄ RUNDĘ" in message:
            self._toggle_game_panel(True)
            self._draw_hangman(0)
            self.current_errors = 0
            self._sync_timer(0)
            self.lbl_word.config(fg="black")

        # Pauza gry
        if "Za mało graczy, gra wstrzymana" in message:
            self._toggle_game_panel(False)
            self._stop_timer()
            self.current_errors = 0
            self._reset_info_labels()

        # Synchronizacja Czasu
        match_time = re.search(r"CZAS:\s+(\d+)s", message)
        if match_time:
            self._sync_timer(float(match_time.group(1)))

        # Rysowanie Wisielca
        match = re.search(r">\s+.*?Wisielec:\s+(\d+)/7", message)
        if match:
            errors = int(match.group(1))
            if errors != self.current_errors:
                self.current_errors = errors
                self._draw_hangman(errors)

    def _draw_hangman(self, step):
        """Rysuje wisielca na podstawie liczby błędów."""
        self.canvas.delete("all")
        clr = "black"
        width = 4
        off_x, off_y = 70, 70

        # Rysowanie szubienicy
        coords = [
            (20, 280, 120, 280),
            (70, 280, 70, 20),
            (70, 20, 180, 20),
            (180, 20, 180, 50)
        ]
        for (x1, y1, x2, y2) in coords:
            self.canvas.create_line(
                x1 + off_x, y1 + off_y,
                x2 + off_x, y2 + off_y,
                width=width, fill=clr
            )

        # Rysowanie ludzika
        if step >= 1:
            self.canvas.create_oval(
                160 + off_x, 50 + off_y, 200 + off_x, 90 + off_y,
                width=width, outline=clr
            )
        if step >= 2:
            self.canvas.create_line(
                180 + off_x, 90 + off_y, 180 + off_x, 170 + off_y,
                width=width, fill=clr
            )
        if step >= 3:
            self.canvas.create_line(
                180 + off_x, 110 + off_y, 150 + off_x, 140 + off_y,
                width=width, fill=clr
            )
        if step >= 4:
            self.canvas.create_line(
                180 + off_x, 110 + off_y, 210 + off_x, 140 + off_y,
                width=width, fill=clr
            )
        if step >= 5:
            self.canvas.create_line(
                180 + off_x, 170 + off_y, 150 + off_x, 220 + off_y,
                width=width, fill=clr
            )
        if step >= 6:
            self.canvas.create_line(
                180 + off_x, 170 + off_y, 210 + off_x, 220 + off_y,
                width=width, fill=clr
            )
        if step >= 7:
            # Rysowanie krzyżyków na oczach i napisu
            eye_coords = [
                (165, 60, 175, 70), (175, 60, 165, 70),
                (185, 60, 195, 70), (195, 60, 185, 70)
            ]
            for (x1, y1, x2, y2) in eye_coords:
                self.canvas.create_line(
                    x1 + off_x, y1 + off_y, x2 + off_x, y2 + off_y,
                    width=3, fill="red"
                )
            self.canvas.create_text(
                125 + off_x, 150 + off_y, text="PRZEGRANA",
                fill="red", font=("Arial", 28, "bold"), angle=30
            )

    # KOMUNIKACJA

    def _send_cmd(self, cmd):
        """Wysyła komendę do serwera."""
        if not self.connected:
            return
        try:
            self.client_socket.send((cmd + "\n").encode('utf-8'))
        except (OSError, socket.error):
            self.disconnect_from_server()

    def action_nick(self):
        """Obsługa przycisku zmiany nicku."""
        nick = simpledialog.askstring("Nick", "Podaj swój nick:")
        if nick:
            self._send_cmd(f"NICK {nick}")

    def action_list(self):
        """Wysyła żądanie listy pokoi."""
        self._send_cmd("LIST")

    def action_create(self):
        """Obsługa tworzenia pokoju."""
        room = simpledialog.askstring("Stwórz Pokój", "Podaj nazwę nowego pokoju:")
        if room:
            self._send_cmd(f"CREATE {room}")

    def action_join(self):
        """Obsługa dołączania do pokoju."""
        room = simpledialog.askstring("Dołącz", "Podaj nazwę pokoju:")
        if room:
            self._send_cmd(f"JOIN {room}")

    def action_leave(self):
        """Wysyła komendę opuszczenia pokoju."""
        self._send_cmd("LEAVE")

    def send_message(self):
        """Wysyła wiadomość z pola tekstowego."""
        if not self.connected:
            return
        msg = self.entry_msg.get()
        if msg:
            self._send_cmd(msg)
            self.entry_msg.delete(0, tk.END)

    def connect_to_server(self):
        """Nawiązuje połączenie z serwerem."""
        if self.connected:
            return
        ip_addr = self.entry_ip.get()
        try:
            port = int(self.entry_port.get())
        except ValueError:
            messagebox.showerror("Błąd", "Port musi być liczbą!")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(3.0)
            self.client_socket.connect((ip_addr, port))
            self.client_socket.settimeout(None)
            self.connected = True
            self.btn_connect.config(state="disabled", bg="#dddddd")
            self.btn_disconnect.config(state="normal", bg="#F44336")
            threading.Thread(target=self.receive_loop, daemon=True).start()
        except (OSError, socket.error) as err:
            messagebox.showerror("Błąd połączenia", f"Nie można połączyć:\n{err}")

    def disconnect_from_server(self):
        """Zamyka połączenie i czyści stan klienta."""
        if not self.connected:
            return
        self.connected = False
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
            self.client_socket.close()
        except (OSError, socket.error):
            pass
        self.client_socket = None
        self.btn_connect.config(state="normal", bg="#8BC34A")
        self.btn_disconnect.config(state="disabled", bg="#dddddd")
        self._disable_all_buttons()
        self._toggle_game_panel(False)
        self._clear_logs()
        self._reset_info_labels()
        self.nick_set = False
        self._stop_timer()

    def receive_loop(self):
        """Wątek odbierający wiadomości od serwera."""
        while self.connected:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    break
                msg = data.decode('utf-8', errors='ignore')
                self.root.after(0, self.log, msg.strip())
            except (OSError, socket.error):
                break
        if self.connected:
            self.root.after(0, self.disconnect_from_server)

    def on_closing(self):
        """Obsługa zamknięcia okna."""
        self.disconnect_from_server()
        self.root.destroy()
        sys.exit(0)


def signal_handler(*args):
    """Obsługa sygnału przerwania (Ctrl+C)."""
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main_root = tk.Tk()
    client = HangmanClient(main_root)

    def check():
        """Loop dla Tkinter, aby obsługiwał sygnały systemowe."""
        main_root.after(500, check)
    main_root.after(500, check)
    main_root.mainloop()
