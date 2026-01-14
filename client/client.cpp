#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <sys/epoll.h>
#include <errno.h>
#include <error.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <iostream>

using namespace std;

int main(int argc, char ** argv){
    if(argc != 3) error(1, 0, "Użycie: ./client <ip> <port>");

    addrinfo hints{.ai_family = AF_INET, .ai_socktype = SOCK_STREAM};
    addrinfo *res;

    if(getaddrinfo(argv[1], argv[2], &hints, &res) != 0) error(1, errno, "getaddrinfo");

    int fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if(connect(fd, res->ai_addr, res->ai_addrlen) == -1) error(1, errno, "connect");

    freeaddrinfo(res);

    int epollfd = epoll_create1(0);
    epoll_event ee;
    
    ee.events = EPOLLIN;
    ee.data.fd = STDIN_FILENO;
    epoll_ctl(epollfd, EPOLL_CTL_ADD, STDIN_FILENO, &ee);
    
    ee.events = EPOLLIN | EPOLLRDHUP;
    ee.data.fd = fd;
    epoll_ctl(epollfd, EPOLL_CTL_ADD, fd, &ee);

    char buff[512];

    while(1){
        int ile = epoll_wait(epollfd, &ee, 1, -1);
        if (ile == -1) error(1, errno, "epoll error");

        if (ee.events & (EPOLLRDHUP|EPOLLHUP|EPOLLERR)){
            printf("Serwer rozłączył połączenie.\n");
            close(fd);
            break;
        }

        if(ee.events & EPOLLIN){
            if(ee.data.fd == STDIN_FILENO){
                ssize_t received = read(STDIN_FILENO, buff, sizeof(buff)-1);
                if(received > 0) {
                     write(fd, buff, received);
                }
            }
            else if (ee.data.fd == fd) {
                ssize_t received = read(fd, buff, sizeof(buff)-1);
                if (received > 0) {
                    buff[received] = 0;
                    printf("%s", buff); 
                }
            }
        }
    }
    return 0;
}