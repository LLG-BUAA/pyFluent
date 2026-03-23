#ifndef REGRESSION_H
#define REGRESSION_H

#include "udf.h"

/**
 * @brief 利用二分法根据总热流 Q 求解表面温度 (K)
 * @param Q 总热流 (W/m2)
 * @param T_f 燃料表面温度 (K) 用于收敛
 * @param c 单元格索引
 * @param tc 线程索引
 * @return 表面温度 (K)
 * @note 该函数会修改 C_UDMI(c, tc, 39) 和 燃速相关的 UDM 值
 */
real Calc_T_By_Q(real Q, real T_f, cell_t c, Thread *tc);

#endif /* REGRESSION_H */
