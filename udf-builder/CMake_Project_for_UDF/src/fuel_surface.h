#ifndef FUEL_SURFACE_H
#define FUEL_SURFACE_H

#ifndef EPS_SMALL
#define EPS_SMALL 1e-12
#endif

#include "udf.h"

/**
 * @brief 计算燃料表面方程，并将结果存入 UDM
 */
void Calc_Equation(cell_t c, Thread *tc, face_t f, Thread *tf);

/* 温度边界条件 */
DEFINE_PROFILE(fuel_wall_temperature, tf, i);

#endif /* FUEL_SURFACE_H */
