#ifndef KINETICS_H
#define KINETICS_H

#include "udf.h"
#include <math.h>

/* 网格参数 */
#define D 0.014                /* 燃料管道直径 (m) */
#define L 0.150                /* 燃料管道长度 (m) */

/* 夹带参数 */
#define a_ent ((100.0e-14)*1.0)     // 5.0e-14 8.0e-14
#define lambda 1.5
#define theta 1.5

/* 物性及常数（宏定义） */
#define R 8.314                   /* 通用气体常数 (J/mol-K) */
#define T_c32h66_vapor 600        /* C32H66的蒸气温度 (K) */
#define MassFraction_PE 0.00        /* PE的质量分数 */
#define Rho_Fuel_PE 941.086         /* PE密度 (kg/m3) */
#define Hf_Fuel_PE_mol -53170613    /* PE标准生成焓 (j/kmol) */

#define MassFraction_Paraffin 1     /* C32H66的质量分数 */
#define Rho_Fuel_Paraffin 920.0     /* C32H66密度 (kg/m3) */
#define Hf_Fuel_Paraffin_mol -967800e3  /* C32H66标准生成焓 (j/kmol) */
#define Hf_Fuel_Paraffin_gas_mol -7.04e+08  /* C32H66气体标准生成焓 (j/kmol) */

#define Wt_Paraffin 450.8664        /* C32H66分子量 */
#define Wt_H2 2.01588               /* H2分子量, 单位 g/mol */
#define Wt_C2H4 28.05418            /* C2H4分子量, 单位 g/mol */
#define MassFraction_H2 (MassFraction_Paraffin * (Wt_H2 / Wt_Paraffin))     /* H2的质量分数 */
#define MassFraction_C2H4 (1 - MassFraction_H2)                             /* C2H4的质量分数 */

#define Hf_Fuel_Paraffin_kg (Hf_Fuel_Paraffin_mol / Wt_Paraffin) /* C32H66标准生成焓 (j/kg) */

/* 石蜡物性 */
#define Ta 298.15                   /* 参考温度 (K) */
#define Cs 2030                     /* 固体比热 (J/kg-K) */
#define Tm 339.6                    /* 熔点 (K) */
#define Lm 167.2e3                  /* 熔化潜热 (J/kg) */
#define Cl 2370                     /* 液体比热 (J/kg-K) */
#define Tv T_c32h66_vapor           /* 蒸发温度 (K) */
#define Lv 163.5e3                  /* 气化潜热 (J/kg) */
#define h_p 2400e3                  /* 热解潜热 (J/kg) */
#define Cg 5000                     /* 气体比热 (J/kg-K) */
#define mu_l 7.8e-3                 /* 液体粘度 (Pa·s) */

/* 根据体积分数公式计算 */
#define Rho_Fuel (1.0 / ((MassFraction_PE / Rho_Fuel_PE) + (MassFraction_Paraffin / Rho_Fuel_Paraffin))) /* 燃料密度 (kg/m3) */
#define VolFraction_Paraffin (Rho_Fuel * MassFraction_Paraffin / Rho_Fuel_Paraffin)
#define VolFraction_PE (Rho_Fuel * MassFraction_PE / Rho_Fuel_PE)

/* 函数声明 */
/**
 * @brief 计算 PE 燃烧（Arrhenius）反应产生的燃速，单位 m/s
 */
real PE_Arrhenius_Reg(real T);

/**
 * @brief 计算 C32H66（Paraffin）蒸发产生的燃速，单位 m/s
 */
real Paraffin_Evapor_Reg(real T);

/**
 * @brief 计算 C32H66（Paraffin）夹带产生的燃速，单位 m/s
 * @param Reg 总燃速，单位 m/s
 * @param m_dot_x 质量流量，单位 kg/s
 * @param rho_g 气体密度，单位 kg/m3
 * @return 夹带燃速，单位 m/s
 */
real Calc_Ent_Reg(real Reg, real m_dot_x, real rho_g);

/**
 * @brief 计算燃料总燃速，单位 m/s
 * @param r_pe PE燃速，单位 m/s
 * @param r_wax 石蜡燃速，单位 m/s
 * @return 燃料总燃速，单位 m/s
 */
real Calc_Fuel_Reg(real r_pe, real r_wax);

#endif /* KINETICS_H */
