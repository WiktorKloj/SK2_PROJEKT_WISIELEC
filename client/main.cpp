#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <iostream>

using namespace std;

string make_packet(const string& payload)
{
    uint32_t len=htonl(payload.size());
    string out;
    out.append(reinterpret_cast<char*>(&len),4);
    out.append(payload);
    return out;
}

int main(int argc, char* argv[])
{
    if(argc!=3)
    {
        cerr<<"Poprawne Użycie: client <ip> <port>\n";
        return 1;
    }
    int fd=socket(AF_INET,SOCK_STREAM,0);
    sockaddr_in addr{};
    addr.sin_family=AF_INET;
    addr.sin_port=htons(std::atoi(argv[2]));
    inet_pton(AF_INET,argv[1], &addr.sin_addr);
    if(connect(fd, (sockaddr*)&addr, sizeof(addr))<0)
    {
        perror("Błąd połączenia");
        return 1;
    }
    string line;
    while (getline(cin,line))
    {
        string pkt=make_packet(line);
        send(fd,pkt.data(),pkt.size(),0);
        char buf[4096];
        ssize_t n=recv(fd,buf,sizeof(buf),0);
        if(n<=0)
        {
            break;
        }
        uint32_t len;
        memcpy(&len, buf,4);
        len=ntohl(len);
        string msg(buf+4,len);
        cout<<msg<<"\n";
    }
    close(fd);
}