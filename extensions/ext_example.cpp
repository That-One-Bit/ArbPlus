/*
 * ArbPlus C++ Extension Example
 * @arbplus-meta name="ext_cpp"
 * @arbplus-meta version="1.0"
 * @arbplus-meta author="ArbPlus"
 * @arbplus-meta description="C++ extension demonstrating the ArbPlus extension ABI"
 * @arbplus-meta dependencies="libstdc++"
 * @arbplus-meta languages="c++"
 *
 * This file demonstrates the C++ extension ABI for ArbPlus.
 * Compile: g++ -shared -fPIC -o ext_cpp.so ext_cpp.cpp
 * Load:    loadExt("./ext_cpp.cpp", "c++");
 *
 * Differences from C version:
 * - Uses extern "C" to prevent name mangling on the entry point
 * - Can use C++ classes for registration
 * - RAII for memory management
 */

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

// --- ArbPlus value marshaling types (same as C version) ---

typedef enum {
    ARB_INT = 0,
    ARB_FLOAT = 1,
    ARB_STRING = 2,
    ARB_BOOL = 3
} ArbType;

typedef struct {
    ArbType type;
    union {
        long long int_val;
        double float_val;
        char* str_val;
        int bool_val;
    } data;
} ArbValue;

// --- Function pointer type ---
typedef ArbValue (*ExtFunc)(int argc, ArbValue* args);

// --- Registration table ---
typedef struct {
    void (*register_func)(const char* name, ExtFunc func);
    void (*register_hook)(const char* builtin_name, ExtFunc hook);
} ArbEngine;

// --- Helper functions ---
static ArbValue make_int(long long v) {
    ArbValue r;
    r.type = ARB_INT;
    r.data.int_val = v;
    return r;
}

static ArbValue make_string(const char* s) {
    ArbValue r;
    r.type = ARB_STRING;
    r.data.str_val = (char*)s;
    return r;
}

static ArbValue make_float(double v) {
    ArbValue r;
    r.type = ARB_FLOAT;
    r.data.float_val = v;
    return r;
}

// --- Extension function: compute average of integers ---
ArbValue ext_average(int argc, ArbValue* args) {
    if (argc == 0) return make_float(0.0);
    long long sum = 0;
    int count = 0;
    for (int i = 0; i < argc; i++) {
        if (args[i].type == ARB_INT) {
            sum += args[i].data.int_val;
            count++;
        }
    }
    if (count == 0) return make_float(0.0);
    return make_float((double)sum / count);
}

// --- Extension function: uppercase a string using C++ std::string ---
ArbValue ext_upper(int argc, ArbValue* args) {
    if (argc > 0 && args[0].type == ARB_STRING) {
        std::string s(args[0].data.str_val);
        for (size_t i = 0; i < s.size(); i++) {
            if (s[i] >= 'a' && s[i] <= 'z') {
                s[i] -= 32;
            }
        }
        static char buf[4096];
        strncpy(buf, s.c_str(), sizeof(buf) - 1);
        buf[sizeof(buf) - 1] = '\0';
        return make_string(buf);
    }
    return make_string("");
}

// --- C++ class-based registration wrapper ---
class ArbPlusExtension {
public:
    static ArbValue average_wrapper(int argc, ArbValue* args) {
        return ext_average(argc, args);
    }
    static ArbValue upper_wrapper(int argc, ArbValue* args) {
        return ext_upper(argc, args);
    }
};

// --- Entry point: extern "C" prevents name mangling ---
extern "C" void arbplus_register(ArbEngine* engine) {
    engine->register_func("ext.average", ArbPlusExtension::average_wrapper);
    engine->register_func("ext.upper", ArbPlusExtension::upper_wrapper);
}
