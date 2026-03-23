#include "udf.h"


DEFINE_ON_DEMAND(Hello_Fluent)
{
    Message("2\n");
    Message("Hello, Fluent UDF! This is a simple test of compiling and loading a UDF in Fluent.\n");
}

DEFINE_ON_DEMAND(Hello_Fluent_Builtin)
{
    Message("2 Build in\n");
    Message("Hello, Fluent UDF! This is a simple test of compiling and loading a UDF in Fluent.\n");
}
