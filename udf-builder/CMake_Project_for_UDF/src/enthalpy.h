#ifndef ENTHALPY_H
#define ENTHALPY_H

#include "udf.h"
#include <math.h>

/**
 * @brief 计算 C2H4 的焓值，单位 J/kg
 */
real Calc_H_C2H4(real T);

/**
 * @brief 计算 H2 的焓值，单位 J/kg
 */
real Calc_H_H2(real T);

/**
 * @brief 计算 产物 的焓值，单位 J/kg
 * @param T 温度，单位 K
 * @return 产物 的焓值，单位 J/kg
 */
real Calc_H_Fuel(real T);

/**
 * @brief 计算 PE 产物的焓值，单位 J/kg
 * @param T 温度，单位 K
 * @return PE 的焓值，单位 J/kg
 */
real Calc_H_PE_Add(real T);

/**
 * @brief 计算 C32H66 产物的焓值，单位 J/kg
 * @param T 温度，单位 K
 * @return C32H66 的焓值，单位 J/kg
 */
real Calc_H_Paraffin_Add(real T);

/**
 * @brief 计算 PE 的热流，单位 W/m2
 * @param T 温度，单位 K
 * @param r_pe 燃速，单位 m/s
 * @return PE 的热流，单位 W/m2
 */
real Calc_Q_PE(real T, real r_pe);

/**
 * @brief 计算 C32H66 的气化热 Qs_Paraffin，单位 J/kg
 * @param T 温度，单位 K
 * @return 石蜡熔化热量，单位 J/kg
 */
real Calc_Delta_H_Paraffin_Lq(real T);

/**
 * @brief 计算 C32H66 的气化热 Qs_Paraffin，单位 J/kg
 * @param T 温度，单位 K
 * @return 石蜡熔化＋蒸发热量，单位 J/kg
 */
real Calc_Delta_H_Paraffin_Lq_Lv(real T);

/**
 * @brief 计算 C32H66 的热流，单位 W/m2
 * @param T 温度，单位 K
 * @param r_wax 燃速，单位 m/s
 * @param r_v 燃速，单位 m/s
 * @return C32H66 的热流，单位 W/m2
 */
real Calc_Q_Paraffin(real T, real r_wax, real r_v);

/**
 * @brief 计算燃料总消耗热流 Q_fuel，单位 W/m2
 * @param T 温度，单位 K
 * @param r_pe PE燃速，单位 m/s
 * @param r_wax 石蜡燃速，单位 m/s
 * @param r_v 燃速，单位 m/s
 * @return 燃料总消耗热流，单位 W/m2
 */
real Calc_Q_Fuel(real T, real r_pe, real r_wax, real r_v);

#endif /* ENTHALPY_H */
