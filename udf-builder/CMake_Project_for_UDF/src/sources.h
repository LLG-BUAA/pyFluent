#ifndef SOURCES_H
#define SOURCES_H

#include "udf.h"

/* 声明各源项 UDF */
DEFINE_SOURCE(Total_Mass_Source, c, tc, dS, eqn);
DEFINE_SOURCE(X_Mom_Source, c, tc, dS, eqn);
DEFINE_SOURCE(Y_Mom_Source, c, tc, dS, eqn);
DEFINE_SOURCE(Z_Mom_Source, c, tc, dS, eqn);
DEFINE_SOURCE(C2H4_Mass_Source, c, tc, dS, eqn);
DEFINE_SOURCE(C32H66_Mass_Source, c, tc, dS, eqn);
DEFINE_SOURCE(Energy_Source_t, c, tc, dS, eqn);

/* on-demand UDF */
DEFINE_ON_DEMAND(Non_Source);
DEFINE_ON_DEMAND(Vari_Source);
DEFINE_ON_DEMAND(Constan_Sources);

#endif /* SOURCES_H */
