#include <iostream>
#include <climits>

#if defined(__GNUC__)
__attribute__((noinline))
#endif
bool check_signed_overflow_assumption(int x) {
    return (x + 1) > x;
}

int main() {
    int val = 0;
    int dummy = 0;

    if (!(std::cin >> val >> dummy)) {
        val = 2147483647;
    }

    std::cout << "--- SIGNED OVERFLOW ASSUMPTION TEST ---\n";
    std::cout << "Input value: " << val << "\n";

    bool result = check_signed_overflow_assumption(val);
    std::cout << "Result of (val + 1 > val): " << (result ? "YES" : "NO") << "\n";

    return 0;
}
