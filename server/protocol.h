#pragma once
#include <string>
#include <cstdint>
#include <arpa/inet.h>

inline std::string make_packet(const std::string& payload)
{
    uint32_t len = htonl(payload.size());
    std::string out;
    out.append(reinterpret_cast<char*>(&len),4);
    out.append(payload);
    return out;
}