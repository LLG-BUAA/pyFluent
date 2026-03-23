#include "regression.h"
#include "kinetics.h"
#include "enthalpy.h"
#include <math.h>
#include <stdio.h>
#include "udf.h"

#ifndef PI
#define PI 3.14159265359
#endif

real Calc_Wax_Reg_By_T(real T, real m_dot_x, real rho_g) {
    real r_pe = PE_Arrhenius_Reg(T);        // PE 燃速
    real r_ent = 1e-6;                      // 夹带燃速
    real r_v = Paraffin_Evapor_Reg(T);      // 石蜡燃速
    real r_wax = r_v + r_ent;               // 石蜡燃速
    real r = Calc_Fuel_Reg(r_pe, r_wax);    // 初始总燃速
    real tol = 0.001e-3;                     // 容差
    real delta = 0.6;                       // 收敛系数
    int max_iter = 750;                     // 最大迭代次数
    int iter = 0;                           // 当前迭代次数

    while (iter < max_iter) {
        r_ent = Calc_Ent_Reg(r, m_dot_x, rho_g);    // 计算夹带燃速
        r_wax = r_v + r_ent;                        // 更新石蜡燃速
        real r_new = Calc_Fuel_Reg(r_pe, r_wax);    // 更新总燃速

        if (fabs(r_new - r) < tol) {                // 检查收敛条件
            r = r_new;
            break;
        }

        r = r_new * (1.0 - delta) + r * delta; // 更新总燃速
        iter++;
    }

    if (iter >= max_iter) {
        Message("[!!!Warning!!!]: calc_Reg_By_Reg_v did not converge within %d iterations.\n", max_iter);
    }

    return r_wax; // 返回石蜡燃速
}

real calc_eqn(real T, real m_dot_x, real rho_g) {
    real r_pe = PE_Arrhenius_Reg(T);                    // PE 燃速
    real r_wax = Calc_Wax_Reg_By_T(T, m_dot_x, rho_g);  // 石蜡燃速
    real r_v = Paraffin_Evapor_Reg(T);                  // 蒸发燃速

    return Calc_Q_Fuel(T, r_pe, r_wax, r_v); // 计算燃速
}

real solve_equation(real target_q, real T_low, real T_high, real tol, int max_iter, real m_dot_x, real rho_g) {
    real T_mid, eqn_low, eqn_mid;
    real low = T_low;
    real high = T_high;
    for (int i = 0; i < max_iter; i++) {
        T_mid = (low + high) / 2.0;
        eqn_mid = calc_eqn(T_mid, m_dot_x, rho_g);

        if (fabs(eqn_mid - target_q) < tol) {
            return T_mid; // 找到解
        }

        if (eqn_mid < target_q) {
            low = T_mid;
        } else {
            high = T_mid;
        }
    }

    if(T_mid > high) {
        Message("[Error High]\tT = %.2f\tq = %.4f MW/m2\ttarget_Q = %.4f MW/m^2\n", T_mid, eqn_mid * 1e-6, target_q * 1e-6);
        T_mid = high; // 返回高温边界
    }
    else if(T_mid < low) {
        Message("[Error Low]\tT = %.2f\tq = %.4f MW/m2\ttarget_Q = %.4f MW/m^2\n", T_mid, eqn_mid * 1e-6, target_q * 1e-6);
        T_mid = low; // 返回低温边界
    }
    else{        
        Message("T = %.2f\tq = %.4f MW/m2\ttarget_Q = %.4f MW/m^2\n", T_mid, eqn_mid * 1e-6, target_q * 1e-6);
    }

    return T_mid;
}

real Calc_T_By_Q(real q, real T_f, cell_t c, Thread *tc) {
    real delta_T = 0.9;         // 温度松弛系数
    real T = 300.0;             // 温度
    real T_low = Tm * 1.1;      // 低温边界
    real T_high = 1500.0;       // 高温边界
    real tol = 1e2;             // 容限
    int max_iter = 750;         // 最大迭代次数
    real r = 1e-6;              // 总燃速
    real r_pe = 1e-6;           // PE 燃速
    real r_wax = 1e-6;          // 石蜡燃速
    real r_v = 1e-6;            // 蒸发燃速
    real r_ent = 1e-6;          // 夹带燃速

    if (q > 0.001e6) {
        // 求解方程 equation(r)=0 得到 温度 T
        T = solve_equation(q, T_low, T_high, tol, max_iter, C_UDMI(c,tc,39), C_UDMI(c,tc,40));
        T = T * delta_T + T_f * (1.0 - delta_T); // 松弛系数

        r_pe = PE_Arrhenius_Reg(T);        // PE 燃速
        r_v = Paraffin_Evapor_Reg(T);      // 蒸发燃速
        r_wax = Calc_Wax_Reg_By_T(T, C_UDMI(c,tc,39), C_UDMI(c,tc,40));      // 石蜡燃速
        
        r = Calc_Fuel_Reg(r_pe, r_wax);    // 总燃速

        r_ent = Calc_Ent_Reg(r, C_UDMI(c,tc,39), C_UDMI(c,tc,40)); // 计算夹带燃速
    }
    else {
        T = 300.0;          // 默认温度
        T = T * delta_T + T_f * (1.0 - delta_T); // 松弛系数

        r_pe = PE_Arrhenius_Reg(T);         // PE 燃速
        r_wax = r_wax = Calc_Wax_Reg_By_T(T, C_UDMI(c,tc,39), C_UDMI(c,tc,40));        // 默认石蜡燃速
        r_v = Paraffin_Evapor_Reg(T);          // 默认蒸发燃速

        r = Calc_Fuel_Reg(r_pe, r_wax);    // 总燃速
        r_ent = Calc_Ent_Reg(r, C_UDMI(c,tc,39), C_UDMI(c,tc,40)); // 计算夹带燃速

        Message("[Warning]\tq = %.4f kW/m2.", q * 1e-3);
    }

    // 输出结果（以毫米为单位）
    Message("\tr = %.4f mm\tr_pe = %.4f mm\tr_wax = %.4f mm\tr_v = %.4f mm\tr_ent = %.4f mm\n", 
        r * 1e3, r_pe * 1e3, r_wax * 1e3, r_v * 1e3, r_ent * 1e3);

    r_pe = 0;   // 1e-7;

    if (r_v > 10e-3){
        r_v = 10e-3;
    }
    if(r > 20e-3){
        r = 20e-3;
        r_ent = r - r_pe - r_v;
        r_wax = r;
    }

    C_UDMI(c,tc,8) = r;         // 存储当前截面总燃速
    C_UDMI(c,tc,51) = r_pe;     // 存储当前截面 PE 燃速
    C_UDMI(c,tc,52) = r_wax;    // 存储当前截面石蜡燃速
    C_UDMI(c,tc,53) = r_v;      // 存储当前截面蒸发燃速
    C_UDMI(c,tc,54) = r_ent;    // 存储当前截面夹带燃速
    
    return T;
}