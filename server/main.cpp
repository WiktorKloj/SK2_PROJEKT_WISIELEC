#include "server.h"
#include <cstdlib>
#include <iostream>

using namespace std;
int main(int argc, char* argv[])
{
    if(argc!=2)
    {
        cerr<<"Poprawne użycie: server <port>\n";
        return 1;
    }
    uint16_t port=atoi(argv[1]);
    Server s(port);
    s.run();
}