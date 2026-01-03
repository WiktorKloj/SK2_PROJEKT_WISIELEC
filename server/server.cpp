#include "server.h"
#include "protocol.h"
#include <algorithm>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <iostream>
#include <sstream>

using namespace std;

Server::Server(uint16_t port)
{
    listen_fd=socket(AF_INET,SOCK_STREAM,0);
    if(listen_fd<0)
    {
        perror("Błąd gniazda");
        exit(1);
    }
    int opt=1;
    setsockopt(listen_fd,SOL_SOCKET,SO_REUSEADDR,&opt,sizeof(opt));
    sockaddr_in addr{};
    addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=INADDR_ANY;
    addr.sin_port=htons(port);

    if(bind(listen_fd,(sockaddr*)&addr,sizeof(addr))<0)
    {
        perror("Błąd bind-a");
        exit(1);
    }
    if(listen(listen_fd,128)<0)
    {
        perror("Błąd listen");
        exit(1);
    }
    FD_ZERO(&master_set);
    FD_SET(listen_fd,&master_set);
    max_fd=listen_fd;
    cout<<"Serwer nasłuchuje port numer "<<port<<"\n";
}

void Server::run()
{
    while (true)
    {
        fd_set readfds=master_set;
        if(select(max_fd+1,&readfds,nullptr,nullptr,nullptr)<0)
        {
            perror("Błąd select-a");
            exit(1);
        }
        for(int fd=0;fd<=max_fd;++fd)
        {
            if(!FD_ISSET(fd,&readfds))
            {
                continue;
            }
            if(fd==listen_fd)
            {
                accept_client();
            }
            else
            {
                read_from_client(fd);
            }
        }
    }
}

void Server::accept_client()
{
    sockaddr_in caddr{};
    socklen_t len=sizeof(caddr);
    int cfd=accept(listen_fd,(sockaddr*)&caddr,&len);
    if(cfd<0)
    {
        return;
    }
    FD_SET(cfd,&master_set);
    max_fd=max(max_fd,cfd);
    clients[cfd]=Client{cfd,""};
    cout<<"Połączono z klientem (fd="<<cfd<<")\n";
}

void Server::read_from_client(int fd)
{
    char buf[4096];
    ssize_t n=recv(fd,buf,sizeof(buf),0);
    if(n<=0)
    {
        disconnect(fd);
        return;
    }
    Client& c=clients[fd];
    c.in_buffer.append(buf,n);
    while (true)
    {
        if(c.in_buffer.size()<4)
        {
            return;
        }
        uint32_t len;
        memcpy(&len,c.in_buffer.data(),4);
        len=ntohl(len);
        if(c.in_buffer.size()<4+len)
        {
            return;
        }
        string msg=c.in_buffer.substr(4,len);
        c.in_buffer.erase(0,4+len);
        handle_message(fd,msg);
    } 
}

void Server::handle_message(int fd, const string& msg)
{
    istringstream iss(msg);
    string cmd;
    iss >> cmd;
    if(cmd=="nick")
    {
        string nick;
        iss >> nick;
        if(nick.empty())
        {
            string emsg="Nie podano nicku!!!";
            auto pkt=make_packet(emsg);
            send(fd,pkt.data(),pkt.size(),0);
            return;
        }
        if(nick_taken(nick,fd))
        {
            string emsg="Ten nick jest już używany przez innego gracza!!!";
            auto pkt=make_packet(emsg);
            send(fd, pkt.data(),pkt.size(),0);
            return;
        }
        clients[fd].nick=nick;
        cout<<"[nick] fd="<<fd<<" nick="<<nick<<"\n";
    }
    else if(cmd=="l_room")
    {
        ostringstream out;
        out<<"POKOJE\n";
        for(auto& [name,room]:rooms)
        {
            out<<name<<" ("<<room.players.size()<<"/8)\n";
        }
        auto pkt=make_packet(out.str());
        send(fd,pkt.data(),pkt.size(),0);
        return;
    }
    else if(cmd=="c_room")
    {
        string room_name;
        iss >> room_name;
        Client& c=clients[fd];
        if(clients[fd].nick.empty())
        {
            string emsg="Najpierw podaj swój nick!!!";
            auto pkt=make_packet(emsg);
            send(fd, pkt.data(), pkt.size(),0);
            return;
        }
        if(c.room)
        {
            auto &vec=c.room->players;
            vec.erase(remove(vec.begin(),vec.end(),&c),vec.end());
            c.room=nullptr;
        }
        if(rooms.count(room_name))
        {
            string emsg="Pokój o podanej nazwie już istnieje!!!";
            auto pkt=make_packet(emsg);
            send(fd,pkt.data(),pkt.size(),0);
            return;
        }
        Room& r=rooms[room_name];
        r.name=room_name;
        r.players.push_back(&c);
        c.room=&r;
        cout<<"[c_room] fd="<<fd<<" room="<<room_name<<"\n";
    }
    else if(cmd=="j_room")
    {
        Client& c=clients[fd];
        if(clients[fd].nick.empty())
        {
            string emsg="Najpierw podaj swój nick!!!";
            auto pkt=make_packet(emsg);
            send(fd, pkt.data(), pkt.size(),0);
            return;
        }
        string room_name;
        iss>>room_name;
        if(!rooms.count(room_name))
        {
            string emsg="Pokój o podanej nazwie nie istnieje!!!";
            auto pkt=make_packet(emsg);
            send(fd,pkt.data(),pkt.size(),0);
            return;
        }
        if(c.room)
        {
            auto &vec=c.room->players;
            vec.erase(remove(vec.begin(),vec.end(),&c),vec.end());
            c.room=nullptr;
        }
        Room& r=rooms[room_name];
        if(r.players.size()>=8)
        {
            string emsg="Pokój jest pełny!!!";
            auto pkt=make_packet(emsg);
            send(fd,pkt.data(),pkt.size(),0);
            return;
        }
        r.players.push_back(&c);
        c.room=&r;
        cout<<"[j_room] fd="<<fd<<" room="<<room_name<<"\n";
    }
    else
    {
        cout<<"[UNKNOWN] fd="<<fd<<" msg="<<msg<<"\n";
    }
    string reply=make_packet("Błędna komenda");
    send(fd,reply.data(),reply.size(),0);
}

void Server::disconnect(int fd)
{
    Client& c=clients[fd];
    if(c.room)
    {
        auto& vec=c.room->players;
        vec.erase(remove(vec.begin(),vec.end(),&c),vec.end());
    }
    cout<<"Klient rozłączony (fd="<<fd<<")\n";
    close(fd);
    FD_CLR(fd,&master_set);
    clients.erase(fd);
}

bool Server::nick_taken(const string& nick, int c_fd) const
{
    for(const auto& [fd,client]:clients)
    {
        if(fd!=c_fd && client.nick==nick)
        {
            return true;
        }
    }
    return false;
}