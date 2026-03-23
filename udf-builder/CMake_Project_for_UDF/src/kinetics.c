#include "kinetics.h"
#include "mass_flux_calculator.h"
#include <math.h>

int Ent_Enable = 1;  /* 夹带源项开关 */

real PE_Arrhenius_Reg(real T)
{
    real PRE_EXP = 2678.1;
    real ACTIVE_ENRGY = 125604;
    real Reg_Rate = PRE_EXP * exp(-ACTIVE_ENRGY / (R * T));
    /* 限制上下界 */
    Reg_Rate = (Reg_Rate > 2.0e-6) ? Reg_Rate : 2.0e-6;
    Reg_Rate = (Reg_Rate < 5.0e-3) ? Reg_Rate : 5.0e-3;
    return Reg_Rate; // m/s * Rho_Fuel_PE * VolFraction_PE
}

real Paraffin_Evapor_Reg(real T)
{
    real PRE_EXP = 0.1 * 2678.1; // 0.15 * 1.9e2;// 7.6e14; // 
    real ACTIVE_ENRGY = 125604;// 0.68 * 0.962 * 190 * 1e3 / 2.0;
    real Reg_Rate = PRE_EXP * exp(-ACTIVE_ENRGY / (R * T));
    /* 限制上下界 */
    // Reg_Rate = (Reg_Rate > 2.0e-6) ? Reg_Rate : 2.0e-6;
    // Reg_Rate = (Reg_Rate < 5.0e-3) ? Reg_Rate : 5.0e-3;
    return Reg_Rate; // m/s * Rho_Fuel_Paraffin * VolFraction_Paraffin
}

real Calc_Ent_Reg(real Reg, real m_dot_x, real rho_g)
{
    if (Ent_Enable < 0.5)
        return 0.0;

    if (m_dot_x < 1e-6)
        return 1e-6;

    // real D = 0.014;          /* m */
    // real a_ent = 100.0 * 1e-14;      // 5.0e-14 8.0e-14
    // real lambda = 1.5;
    // real theta = 1.5;
    real G = 4 * m_dot_x / (PI * D * D);

    // 设置 rho_g 上下限
    // rho_g = 5.0; * (1 / pow(rho_g, theta))
    
    real Reg_ent = a_ent * pow(G, 2 * lambda) / pow(Reg, theta);
    return Reg_ent;     // m / s
}

real Calc_Fuel_Reg(real r_pe, real r_wax)
{
    real m_dot_all_per_m2 = r_pe * Rho_Fuel_PE * VolFraction_PE + r_wax * Rho_Fuel_Paraffin * VolFraction_Paraffin; // kg / m^2 s
    return m_dot_all_per_m2 / Rho_Fuel; // m / s
}

DEFINE_ON_DEMAND(Enable_Ent_Source)
{
    Ent_Enable = 1;
    Message("夹带源项已启用。\n");
}

DEFINE_ON_DEMAND(Disable_Ent_Source)
{
    Ent_Enable = 0;
    Message("夹带源项已禁用。\n");
}