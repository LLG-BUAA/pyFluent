#include "udf.h"
#include "fuel_surface.h"
#include "kinetics.h"
#include "regression.h"
#include "enthalpy.h"
#include "mass_flux_calculator.h"  /* 质量流量计算函数 */
#include <math.h>
#include <stdio.h>

#ifndef TOL
#define TOL 1e-6
#endif

#ifndef PI
#define PI 3.14159265359
#endif


/* 燃料壁面温度边界条件 */
DEFINE_PROFILE(fuel_wall_temperature, tf, i)
{
    cell_t c;
    Thread *tc;
    face_t f;

    begin_f_loop(f, tf)
    {
        /* 标记燃料壁面单元 */
        c = F_C0(f, tf);
        tc = F_C0_THREAD(f, tf);
        C_UDMI(c,tc,0) = 1;

        /* 初始化夹带量为0，在Calc_Equation(c, tc, f, tf)中会被更新 */
        C_UDMI(c,tc,46) = 1e-7;
        
        // 获取当前cell坐标信息
        real xc[ND_ND]; // 定义一个数组 xc，用于存储单元质心的坐标
        C_CENTROID(xc, c, tc); // 获取单元质心坐标
        real x = xc[0] * 1000; // 将 x 坐标转换为 mm 单位
        real m_dot_fit_here = cal_m_dot_x_use_fit_function(x);
        if (m_dot_fit_here < 1e-4)
            m_dot_fit_here = 1e-3; // 设置一个默认值，避免过小的质量流率

        /* 初始化通道流量 与 平均密度 */
        if (C_UDMI(c,tc,43) < 0.5)
            C_UDMI(c,tc,39) = m_dot_fit_here;
            // C_UDMI(c,tc,39) = Calc_Mdot_At_Cell(c, tc);
        
        /* 计算燃料表面方程 */
        // if (NNULLP(THREAD_STORAGE(tc, SV_T_RG)))
        Calc_Equation(c, tc, f, tf);

        /* 利用 mass_flux_calculator 计算当前截面质量流量 与 平均密度，存入 UDM 39 和 40，并标记燃料通道 cell*/
        // C_UDMI(c,tc,39) = Calc_Mdot_At_Cell(c, tc);
        C_UDMI(c,tc,39) = m_dot_fit_here;

        /* 设置温度 */
        if (C_UDMI(c,tc,1) < 0.5)
            F_PROFILE(f, tf, i) = 900;
        else
            F_PROFILE(f, tf, i) = C_UDMI(c,tc,5);
    }
    end_f_loop(f, tf)
}


/* 全局燃料物性（可统一抽出到 properties.h，这里直接使用宏定义） */
// extern const real Rho_Fuel;   /* 由 kinetics 模块或全局定义 */

/* 计算燃料表面方程，各变量计算后存入对应的 C_UDMI 下标 */
void Calc_Equation(cell_t c, Thread *tc, face_t f, Thread *tf)
{
    real Q_con, Q_rad, Q_total;
    real Titer, area, thk_c;
    real T_f = F_T(f, tf);  /* 燃料表面温度 */
    int flag = 0;
    real prt, alpha;
    real mu = C_MU_L(c,tc);
    real mu_t = C_MU_T(c,tc);
    alpha = rng_alpha(1.0, mu + mu_t, mu);
    prt = mu_t / ((mu + mu_t) * alpha - mu);

    /* 获得面面积向量及相关量 */
    real A[ND_ND] = {0};
    F_AREA(A, f, tf);
    area = NV_MAG(A);

    // 详见 "D:\Workshop\Workbench\DPM\dpm-v1-1_files\dp0\FLU-4\Fluent\xy-plot-area" 
    // C_UDMI(c,tc,57) = area; /* 存储当前截面面积 */ // = 半径 0.007 * face 的宽度 并不带 2 Pi

    thk_c = C_VOLUME(c,tc) / area;

    /* 计算气固换热 */
    Q_con = -2 * C_K_EFF(c,tc,prt) * (F_T(f,tf) - C_T(c,tc)) / thk_c;
    Q_rad = 0.0 * Q_con; /* 计算辐射换热，假设为 0 */
    Q_total = Q_con + Q_rad;

    real Q_delta = 0.95;      /* 热流松弛系数 */
    real Q_temp = Q_total;
    // 最小为 0.001e6 W/m2    
    if (Q_temp < 0.001e6)
        Q_temp = 0.001e6;
    Q_temp = Q_temp * Q_delta + C_UDMI(c,tc,13) * (1.0 - Q_delta); /* 计算当前截面热流密度 */

    /* 计算壁温 */
    Titer = Calc_T_By_Q(Q_temp, T_f, c, tc);  /* 计算当前截面温度 */

    /* 存储燃速 */
    // C_UDMI(c,tc,8) = r;         // 存储当前截面总燃速
    // C_UDMI(c,tc,51) = r_pe;     // 存储当前截面 PE 燃速
    // C_UDMI(c,tc,52) = r_wax;    // 存储当前截面石蜡燃速
    // C_UDMI(c,tc,53) = r_v;      // 存储当前截面蒸发燃速
    // C_UDMI(c,tc,54) = r_ent;    // 存储当前截面夹带燃速
    C_UDMI(c,tc,47) = C_UDMI(c,tc,8) * Rho_Fuel * MassFraction_PE;                  /* 存储当前截面 PE 量 Gf_pe */
    C_UDMI(c,tc,46) = C_UDMI(c,tc,54) * Rho_Fuel_Paraffin * VolFraction_Paraffin;   /* 存储当前截面石蜡夹带量 Gf_ent */

    C_UDMI(c,tc,9) = Rho_Fuel * C_UDMI(c,tc,8); /* 存储当前截面总燃速 Gf */

    C_UDMI(c,tc,3) = thk_c;
    C_UDMI(c,tc,4) = area;
    C_UDMI(c,tc,5) = Titer;
    C_UDMI(c,tc,6) = T_f;
    C_UDMI(c,tc,7) = C_T(c,tc);
    // C_UDMI(c,tc,9) = Rho_Fuel * C_UDMI(c,tc,8); /* 存储当前截面总燃速 Gf */

    if (NNULLP(THREAD_STORAGE(tc, SV_T_RG)))
    {
        C_UDMI(c,tc,10) = -NV_DOT(C_T_RG(c,tc), A) / NV_MAG(A);
        flag = 1;
    }
    else
        C_UDMI(c,tc,10) = C_UDMI(c,tc,10);

    C_UDMI(c,tc,11) = C_K_EFF(c,tc,prt);
    C_UDMI(c,tc,12) = Q_total;
    C_UDMI(c,tc,13) = Q_temp;
    // C_UDMI(c,tc,13) = Calc_Qs_f(Titer, C_UDMI(c,tc,8), C_UDMI(c,tc,41));
    // C_UDMI(c,tc,14) = C_UDMI(c,tc,13) + Hf_Fuel_Paraffin_kg * C_UDMI(c,tc,9);
    // C_UDMI(c,tc,15) = C_UDMI(c,tc,14) - C_UDMI(c,tc,12);
    // C_UDMI(c,tc,16) = Hf_Fuel_Paraffin_kg * C_UDMI(c,tc,9);
    C_UDMI(c,tc,17) = C_K_EFF(c,tc,prt) * (F_T(f,tf) - C_T(c,tc)) / (thk_c / 2);

    C_UDMI(c,tc,18) = Calc_H_Fuel(Titer);
    C_UDMI(c,tc,19) = Calc_H_Paraffin_Add(Titer);
    C_UDMI(c,tc,20) = Calc_H_PE_Add(Titer);

    C_UDMI(c,tc,21) = A[0] / NV_MAG(A);
    C_UDMI(c,tc,22) = A[1] / NV_MAG(A);
    C_UDMI(c,tc,24) = -(F_T(f,tf) - C_T(c,tc)) / thk_c * 2;
    C_UDMI(c,tc,25) = C_UDMI(c,tc,23) / C_UDMI(c,tc,10);

    // 测试用 - 存储当前截面体积
    C_UDMI(c,tc,58) = C_VOLUME(c, tc);

    // 获取当前cell的y坐标
    real x[ND_ND];
    real y;
    C_CENTROID(x,c,tc);
    y = x[1];
    C_UDMI(c,tc,59) = y * 2.0; /* 存储燃料表面直径 */

    // 计算当前截面石蜡夹带流量 kg/s = 燃速 m/s * 面积 m2 * 石蜡密度 kg/m3
    C_UDMI(c,tc,50) = C_UDMI(c,tc,46) * area * 2.0 * PI; /* 存储当前截面石蜡夹带流量，为DPM注入做准备 */
}
