#include <sys/socket.h>
#include <sys/types.h>
#include <sys/epoll.h>
#include <netdb.h>
#include <unistd.h>
#include <errno.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <iostream>
#include <algorithm>
#include <ctime>
#include <sstream>
#include <error.h>

using namespace std;

#define MAX_EVENTS 32
#define MAX_PLAYERS_IN_ROOM 8
#define MAX_ERRORS 7 // Ile części wisielca (głowa, tułów, ręce, nogi...)
#define ROUND_TIME_SEC 120 


struct Player {
    int fd;
    string nick;
    string roomName;   // Pusty string = brak pokoju
    int score;         // Punkty ogólne
    int roundErrors;   // Błędy w bieżącej rundzie (części wisielca)
    string usedChars;  // Litery użyte przez gracza w tej rundzie
    bool eliminated;   // Czy odpadł w tej rundzie (skompletował wisielca/dołączył gdy już trwała)
};

struct GameRoom {
    string name;
    vector<int> members; // Lista FD graczy
    string password;     // Hasło do zgadnięcia (np. "WISIELEC")
    string maskedPw;     // Stan widoczny (np. "_ I _ I _ _ _ _")
    bool gameActive;
    struct timespec startTime; // Czas monotoniczny startu rundy
};


map<int, Player> players;
map<string, GameRoom> rooms;
const vector<string> DICTIONARY = {"KOMPUTER", "INTERNET", "PROGRAMOWANIE", "SERWER", "KLIENT", "PROTOKOL", "WISIELEC", "LINUX"};



// Pobiera aktualny czas monotoniczny
struct timespec getMonotonicTime() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts;
}

// Zwraca różnicę czasu w sekundach
double timeDiff(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

void sendTo(int fd, string msg) {
    msg += "\n";
    write(fd, msg.c_str(), msg.length());
}

// Wysyła wiadomość do wszystkich w pokoju
void broadcast(GameRoom &room, string msg) {
    for (int fd : room.members) {
        sendTo(fd, msg);
    }
}

// Generuje status gry (planszę) dla graczy
string getGameStatus(GameRoom &r, int viewerFd = -1) {
    stringstream ss;
    ss << "\n--- POKÓJ: " << r.name << " ---\n";
    ss << "HASŁO: " << r.maskedPw << "\n";
    ss << "CZAS: " << (int)timeDiff(r.startTime, getMonotonicTime()) << "s / " << ROUND_TIME_SEC << "s\n";
    ss << "TABELA WYNIKÓW:\n";
    for(int fd : r.members) {
        Player &p = players[fd];
        ss << (p.fd == viewerFd ? " > " : "   ") 
           << p.nick << " | Pkt: " << p.score << " | Wisielec: " << p.roundErrors << "/" << MAX_ERRORS;
        if(p.eliminated) ss << " [ODPADŁ]";
        if(p.fd == viewerFd) ss << " | Twoje litery: " << p.usedChars;
        ss << "\n";
    }
    return ss.str();
}

void startRound(GameRoom &r) {
    r.gameActive = true;
    r.password = DICTIONARY[rand() % DICTIONARY.size()];
    r.maskedPw = string(r.password.length(), '_');
    r.startTime = getMonotonicTime();

    // Resetuj stan graczy na nową rundę
    for(int fd : r.members) {
        players[fd].roundErrors = 0;
        players[fd].usedChars = "";
        players[fd].eliminated = false;
    }
    
    broadcast(r, "--- ROZPOCZYNAMY NOWĄ RUNDĘ! ---");
    broadcast(r, getGameStatus(r));
    broadcast(r, "Wpisz literę, aby zgadywać (np. 'A')");
}

void endRound(GameRoom &r, string reason) {
    r.gameActive = false;
    broadcast(r, "\n--- KONIEC RUNDY ---");
    broadcast(r, "Powód: " + reason);
    broadcast(r, "Prawidłowe hasło: " + r.password);
    
    // Sprawdź warunki kontynuacji
    if(r.members.size() >= 2) {
        broadcast(r, "Za 3 sekundy nowa runda...");
        sleep(1); 
        startRound(r);
    } else {
        broadcast(r, "Oczekiwanie na graczy (min. 2)...");
    }
}

// Sprawdza, czy wszyscy gracze są wyeliminowani
bool checkAllEliminated(GameRoom &r) {
    for(int fd : r.members) {
        if(!players[fd].eliminated) return false;
    }
    return true;
}

void removePlayerFromRoom(int fd) {
    Player &p = players[fd];
    if(p.roomName.empty()) return;

    if(rooms.count(p.roomName)) {
        GameRoom &r = rooms[p.roomName];
        auto it = find(r.members.begin(), r.members.end(), fd);
        if(it != r.members.end()) {
            r.members.erase(it);
            // Komunikat dla reszty
            for(int mfd : r.members) sendTo(mfd, "Gracz " + p.nick + " opuścił pokój.");
        }

        // Zerowanie punktów gracza po wyjściu (wymóg)
        p.score = 0;
        p.roomName = "";

        // Logika pokoju po wyjściu
        if(r.members.empty()) {
            rooms.erase(r.name);
        } else if (r.members.size() < 2 && r.gameActive) {
            r.gameActive = false;
            broadcast(r, "Za mało graczy, gra wstrzymana.");
        }
    }
}



void handleCommand(int fd, string cmdLine) {
    stringstream ss(cmdLine);
    string cmd, arg;
    ss >> cmd;
    getline(ss, arg);
    if(!arg.empty() && arg[0] == ' ') arg.erase(0, 1);


    transform(cmd.begin(), cmd.end(), cmd.begin(), ::toupper);

    Player &p = players[fd];

    // 1. Ustawianie Nicku (Wymagane na początku)
    if (p.nick.empty()) {
        if (cmd == "NICK") {
            if(arg.empty()) { sendTo(fd, "ERR Musisz podać nick!"); return; }
            // Sprawdź unikalność
            for(auto const& [k, v] : players) {
                if(v.nick == arg) { sendTo(fd, "ERR Nick zajęty!"); return; }
            }
            p.nick = arg;
            sendTo(fd, "OK Witaj " + p.nick);
            sendTo(fd, "Komendy: LIST, CREATE <nazwa>, JOIN <nazwa>");
        } else {
            sendTo(fd, "Najpierw ustaw nick komendą: NICK <twoj_nick>");
        }
        return;
    }

    // 2. Komendy poza pokojem
    if (p.roomName.empty()) {
        if (cmd == "LIST") {
            sendTo(fd, "Dostępne pokoje:");
            for(auto const& [name, r] : rooms) {
                sendTo(fd, "- " + name + " [" + to_string(r.members.size()) + "/8]");
            }
        }
        else if (cmd == "CREATE") {
            if(arg.empty()) { sendTo(fd, "ERR Podaj nazwę pokoju"); return; }
            if(rooms.count(arg)) { sendTo(fd, "ERR Pokój istnieje"); return; }
            
            GameRoom newRoom;
            newRoom.name = arg;
            newRoom.gameActive = false;
            rooms[arg] = newRoom;
            

            handleCommand(fd, "JOIN " + arg);
        }
        else if (cmd == "JOIN") {
            if(!rooms.count(arg)) { sendTo(fd, "ERR Brak pokoju"); return; }
            GameRoom &r = rooms[arg];
            if(r.members.size() >= MAX_PLAYERS_IN_ROOM) { sendTo(fd, "ERR Pokój pełny"); return; }
            
            p.roomName = arg;
            p.score = 0;
            r.members.push_back(fd);
            
            broadcast(r, "Gracz " + p.nick + " dołączył.");
            
            if(r.members.size() >= 2 && !r.gameActive) {
                startRound(r);
            } else if (r.gameActive) {
                // Dołączył w trakcie - czeka (jest wyeliminowany na starcie tej rundy)
                p.eliminated = true; 
                sendTo(fd, "Gra trwa. Poczekaj na nową rundę.");
                sendTo(fd, getGameStatus(r, fd));
            } else {
                sendTo(fd, "Oczekiwanie na drugiego gracza...");
            }
        }
        else {
            sendTo(fd, "Dostępne: LIST, CREATE, JOIN");
        }
        return;
    }

    // 3. Komendy w pokoju
    GameRoom &r = rooms[p.roomName];

    if (cmd == "LEAVE") {
        removePlayerFromRoom(fd);
        sendTo(fd, "Wyszedłeś z pokoju. Komendy: LIST, CREATE, JOIN");
        return;
    }

    // Logika Gry (Zgadywanie)
    if (r.gameActive) {
        if (p.eliminated) {
            sendTo(fd, "Jesteś wyeliminowany lub czekasz na nową rundę. Obserwuj.");
            return;
        }

        // Oczekujemy pojedynczej litery
        if (cmdLine.length() != 1) {
            if (cmd == "GUESS" && arg.length() == 1) {
                cmdLine = arg;
            } else if (cmdLine.length() > 1 && cmd != "GUESS") {
                 sendTo(fd, "Wpisuj pojedyncze litery.");
                 return;
            }
        }
        
        char guess = toupper(cmdLine[0]);
        if (guess < 'A' || guess > 'Z') {
             sendTo(fd, "ERR Tylko litery A-Z");
             return;
        }

        // Walidacja: Czy już użyta?
        if (p.usedChars.find(guess) != string::npos) {
            sendTo(fd, "Już sprawdzałeś tę literę!");
            return;
        }
        // Walidacja: Czy już odsłonięta w haśle?
        if (r.maskedPw.find(guess) != string::npos) {
            sendTo(fd, "Ta litera jest już odkryta!");
            return;
        }

        p.usedChars += guess; 

        // Sprawdzenie czy trafiony
        bool hit = false;
        bool completed = true;
        for (size_t i = 0; i < r.password.length(); i++) {
            if (r.password[i] == guess) {
                r.maskedPw[i] = guess;
                hit = true;
            }
            if (r.maskedPw[i] == '_') completed = false;
        }

        if (hit) {
            sendTo(fd, "TRAFIENIE!");
            if (completed) {
                p.score++;
                broadcast(r, "GRACZ " + p.nick + " ZGADŁ HASŁO! (+1 PKT)");
                endRound(r, "Hasło odgadnięte.");
            } else {
                // Odśwież widok wszystkim
                for(int mfd : r.members) sendTo(mfd, getGameStatus(r, mfd));
            }
        } else {
            p.roundErrors++;
            sendTo(fd, "PUDŁO!");
            if (p.roundErrors >= MAX_ERRORS) {
                p.eliminated = true;
                broadcast(r, "Gracz " + p.nick + " został powieszony i odpada z rundy!");
                for(int mfd : r.members) sendTo(mfd, getGameStatus(r, mfd));
                if(checkAllEliminated(r)) {
                    endRound(r, "Wszyscy gracze wyeliminowani (przegrana).");
                }
            } else {
                 // Odśwież widok
                 for(int mfd : r.members) sendTo(mfd, getGameStatus(r, mfd));
            }
        }
    } else {
        sendTo(fd, "Gra wstrzymana lub oczekiwanie na graczy.");
    }
}



int main(int argc, char ** argv) {
    srand(time(NULL)); 

    if(argc != 2) {
        fprintf(stderr, "Użycie: %s <port>\n", argv[0]);
        return 1;
    }

    // 1. Inicjalizacja Gniazda
    addrinfo hints{.ai_family = AF_INET, .ai_socktype = SOCK_STREAM};
    addrinfo *res;
    if(getaddrinfo(NULL, argv[1], &hints, &res) != 0) error(1, errno, "getaddrinfo");

    int servFd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    int opt = 1;
    setsockopt(servFd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    if(bind(servFd, res->ai_addr, res->ai_addrlen) == -1) error(1, errno, "bind");
    if(listen(servFd, 10) == -1) error(1, errno, "listen");
    freeaddrinfo(res);

    // 2. Epoll
    int epollFd = epoll_create1(0);
    epoll_event ee;
    ee.events = EPOLLIN;
    ee.data.fd = servFd;
    epoll_ctl(epollFd, EPOLL_CTL_ADD, servFd, &ee);

    printf("Serwer Wisielca startuje na porcie %s\n", argv[1]);

    // 3. Pętla Główna
    while(true) {
        // Czekamy 100ms, aby często sprawdzać czas rundy
        int n = epoll_wait(epollFd, &ee, 1, 100); 

        // A. Logika Czasu 
        struct timespec now = getMonotonicTime();
        for(auto &pair : rooms) {
            GameRoom &r = pair.second;
            if(r.gameActive) {
                double elapsed = timeDiff(r.startTime, now);
                if(elapsed >= ROUND_TIME_SEC) {
                    endRound(r, "Czas minął (2 minuty).");
                }
            }
        }

        if (n == -1) {
            if(errno == EINTR) continue;
            error(1, errno, "epoll error");
        }
        if (n == 0) continue;

        // B. Obsługa Sieci
        if (ee.data.fd == servFd) {
            // Nowy klient
            sockaddr_in cAddr;
            socklen_t cLen = sizeof(cAddr);
            int clientFd = accept(servFd, (sockaddr*)&cAddr, &cLen);
            if(clientFd == -1) continue;

            ee.events = EPOLLIN | EPOLLRDHUP;
            ee.data.fd = clientFd;
            epoll_ctl(epollFd, EPOLL_CTL_ADD, clientFd, &ee);

            players[clientFd] = Player{clientFd, "", "", 0, 0, "", false};
            sendTo(clientFd, "Witaj na serwerze WISIELEC!");
            sendTo(clientFd, "Podaj swój nick: NICK <nazwa>");
            printf("Klient podłączony: %d\n", clientFd);
        }
        else {
            // Dane od klienta
            int fd = ee.data.fd;
            if (ee.events & (EPOLLRDHUP | EPOLLHUP | EPOLLERR)) {
                printf("Klient rozłączony: %d\n", fd);
                removePlayerFromRoom(fd);
                players.erase(fd);
                epoll_ctl(epollFd, EPOLL_CTL_DEL, fd, nullptr);
                close(fd);
            }
            else if (ee.events & EPOLLIN) {
                char buffer[512];
                ssize_t count = read(fd, buffer, sizeof(buffer)-1);
                if(count > 0) {
                    buffer[count] = 0;
                    string raw(buffer);
                    // Usuwanie znaków końca linii
                    while(!raw.empty() && (raw.back() == '\n' || raw.back() == '\r')) 
                        raw.pop_back();
                    
                    if(!raw.empty()) handleCommand(fd, raw);
                }
            }
        }
    }
    
    close(servFd);
    close(epollFd);
    return 0;
}