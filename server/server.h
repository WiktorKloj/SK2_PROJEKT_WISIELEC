#pragma once
#include <map>
#include <string>
#include <cstdint>
#include <sys/select.h>
#include <vector>

struct Client;
struct Room
{
    std::string name;
    std::vector<Client*> players;
};

struct Client
{
    int fd;
    std::string in_buffer;
    std::string nick;
    Room* room=nullptr;
};

class Server
{
    public:
        explicit Server(uint16_t port);
        void run();
    private:
        int listen_fd;
        fd_set master_set;
        int max_fd;
        std::map<int, Client> clients;
        std::map<std::string, Room> rooms; 
        void accept_client();
        void read_from_client(int fd);
        void disconnect(int fd);
        void handle_message(int fd,const std::string& msg);
        bool nick_taken(const std::string& nick,int fd) const;
};
