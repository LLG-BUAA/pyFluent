#ifndef MASS_FLUX_CALCULATOR_H
#define MASS_FLUX_CALCULATOR_H

#include "udf.h"
#include <math.h>

#define TOL 1e-6

#ifndef PI
#define PI 3.1415926536
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 拟合截面质量流率函数
 *
 */
void fit_mass_flow_function();

/**
 * @brief 使用拟合函数计算给定 x 坐标处的截面质量流量
 *
 * @param x x 坐标（单位：mm）
 * @return real 计算得到的截面质量流量（单位：kg/s）
 */
real cal_m_dot_x_use_fit_function(real x);

/**
 * @brief 计算二维面法向量（采用90度旋转：(-dy, dx)），结果存放在 normal 中
 *
 * @param f 面
 * @param tf 当前面所在的线程
 * @param normal 存放法向量的数组，长度至少 ND_ND
 */
void compute_face_normal(face_t f, Thread *tf, real normal[ND_ND]);

/**
 * @brief 计算给定 cell 截面总质量流量（单位：kg/s）
 *
 * @param c cell
 * @param tc cell 对应的线程
 * @return real 计算得到的截面总质量流量
 */
real Calc_Mdot_At_Cell(cell_t c, Thread *tc);

#ifdef __cplusplus
}
#endif

#endif /* MASS_FLUX_CALCULATOR_H */
