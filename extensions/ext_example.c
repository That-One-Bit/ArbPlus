/*
 * ArbPlus C Extension Example
 * @arbplus-meta name="ext_c"
 * @arbplus-meta version="1.0"
 * @arbplus-meta author="ArbPlus"
 * @arbplus-meta description="C extension demonstrating the ArbPlus extension ABI"
 * @arbplus-meta dependencies="libc"
 * @arbplus-meta languages="c"
 *
 * This file demonstrates the C extension ABI for ArbPlus.
 * Compile: gcc -shared -fPIC -o ext_c.so ext_c.c
 * Load:    loadExt("./ext_c.c", "c");
 *
 * The exported entry point is arbplus_register(), which receives
 * a pointer to the interpreter's registration table.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* --- ArbPlus value marshaling types --- */

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

/* --- Function pointer type for extension functions --- */
typedef ArbValue (*ExtFunc)(int argc, ArbValue* args);

/* --- Registration table passed to arbplus_register --- */
typedef struct {
    void (*register_func)(const char* name, ExtFunc func);
    void (*register_hook)(const char* builtin_name, ExtFunc hook);
} ArbEngine;

/* --- Helper: create int ArbValue --- */
static ArbValue make_int(long long v) {
    ArbValue r;
    r.type = ARB_INT;
    r.data.int_val = v;
    return r;
}

/* --- Helper: create string ArbValue --- */
static ArbValue make_string(const char* s) {
    ArbValue r;
    r.type = ARB_STRING;
    r.data.str_val = (char*)s;
    return r;
}

/* --- Extension function: double an integer --- */
ArbValue ext_double(int argc, ArbValue* args) {
    if (argc > 0 && args[0].type == ARB_INT) {
        return make_int(args[0].data.int_val * 2);
    }
    return make_int(0);
}

/* --- Extension function: reverse a string --- */
ArbValue ext_reverse(int argc, ArbValue* args) {
    if (argc > 0 && args[0].type == ARB_STRING) {
        char* str = args[0].data.str_val;
        int len = strlen(str);
        char* reversed = (char*)malloc(len + 1);
        for (int i = 0; i < len; i++) {
            reversed[i] = str[len - 1 - i];
        }
        reversed[len] = '\0';
        return make_string(reversed);
    }
    return make_string("");
}

/* --- Entry point: called when the extension is loaded --- */
void arbplus_register(ArbEngine* engine) {
    engine->register_func("ext.double", ext_double);
    engine->register_func("ext.reverse", ext_reverse);
}
