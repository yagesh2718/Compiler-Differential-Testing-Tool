#include <iostream>
#include <cstdint>
#include <climits>

int count_set_bits(uint32_t n) {
    int count = 0;
    while (n > 0) {
        count += (n & 1u);
        n >>= 1u;
    }
    return count;
}

int compute_parity(uint32_t n) {
    return count_set_bits(n) % 2;
}

uint32_t reverse_bits(uint32_t n) {
    uint32_t result = 0;
    for (int i = 0; i < 32; ++i) {
        result = (result << 1u) | (n & 1u);
        n >>= 1u;
    }
    return result;
}

int main() {
    int64_t a = 0;
    int64_t b = 0;

    if (!(std::cin >> a >> b)) {
        std::cerr << "Error: Expected two integers as input.\n";
        return 1;
    }

    uint32_t ua = static_cast<uint32_t>(a);
    uint32_t ub = static_cast<uint32_t>(b);

    std::cout << "--- BITWISE AND BOUNDARY REPORT ---\n";
    std::cout << "Input A: " << a << " (unsigned hex: 0x" << std::hex << ua << std::dec << ")\n";
    std::cout << "Input B: " << b << " (unsigned hex: 0x" << std::hex << ub << std::dec << ")\n";

    std::cout << "Bitwise AND : 0x" << std::hex << (ua & ub) << std::dec << "\n";
    std::cout << "Bitwise OR  : 0x" << std::hex << (ua | ub) << std::dec << "\n";
    std::cout << "Bitwise XOR : 0x" << std::hex << (ua ^ ub) << std::dec << "\n";
    std::cout << "Bitwise NOT A: 0x" << std::hex << (~ua) << std::dec << "\n";

    uint32_t shift_amount = ub & 31u;
    std::cout << "Shift A left by " << shift_amount << " : 0x" 
              << std::hex << (ua << shift_amount) << std::dec << "\n";
    std::cout << "Shift A right by " << shift_amount << " : 0x" 
              << std::hex << (ua >> shift_amount) << std::dec << "\n";

    std::cout << "Popcount A : " << count_set_bits(ua) << "\n";
    std::cout << "Popcount B : " << count_set_bits(ub) << "\n";
    std::cout << "Parity A   : " << compute_parity(ua) << "\n";
    std::cout << "Reverse A  : 0x" << std::hex << reverse_bits(ua) << std::dec << "\n";

    std::cout << "Sign A     : " << (a < 0 ? "NEGATIVE" : (a > 0 ? "POSITIVE" : "ZERO")) << "\n";
    std::cout << "Sign B     : " << (b < 0 ? "NEGATIVE" : (b > 0 ? "POSITIVE" : "ZERO")) << "\n";

    return 0;
}
