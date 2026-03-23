#include "enthalpy.h"
#include "kinetics.h"
#include <math.h>

real Calc_H_C2H4(real T)
{
    /* Aij 参数表，分两组 */
    real Aij_C2H4[2][10] = {
        {-1.163605836e+05,  2.554851510e+03, -1.609746428e+01,  6.625779320e-02,
         -7.885081860e-05,  5.125224820e-08, -1.370340031e-11, 0.0,
         -6.176191070e+03,  1.093338343e+02},
        { 3.408763670e+06, -1.374847903e+04,  2.365898074e+01, -2.423804419e-03,
          4.431395660e-07, -4.352683390e-11,  1.775410633e-15, 0.0,
          8.820429380e+04, -1.371278108e+02}
    };
    
    real H_delta_C2H4;
    if (T < 1000)
    {
        H_delta_C2H4 = R * T * (
            -Aij_C2H4[0][0]*pow(T, -2) + Aij_C2H4[0][1]*pow(T, -1)*log(T) + Aij_C2H4[0][2]
            + Aij_C2H4[0][3]*T/2 + Aij_C2H4[0][4]*pow(T,2)/3 + Aij_C2H4[0][5]*pow(T,3)/4
            + Aij_C2H4[0][6]*pow(T,4)/5 + Aij_C2H4[0][8]/T);
    }
    else
    {
        H_delta_C2H4 = R * T * (
            -Aij_C2H4[1][0]*pow(T, -2) + Aij_C2H4[1][1]*pow(T, -1)*log(T) + Aij_C2H4[1][2]
            + Aij_C2H4[1][3]*T/2 + Aij_C2H4[1][4]*pow(T,2)/3 + Aij_C2H4[1][5]*pow(T,3)/4
            + Aij_C2H4[1][6]*pow(T,4)/5 + Aij_C2H4[1][8]/T);
    }
    return (1e3 * H_delta_C2H4) / Wt_C2H4; // J/kg
}

real Calc_H_H2(real T)
{
    real Aij_H2[2][10] = 
	{
        {4.078323210e+04, -8.009186040e+02, 8.214702010e+00, -1.269714457e-02,  1.753605076e-05, 
            -1.202860270e-08,  3.368093490e-12, 0.000000000e+00, 2.682484665e+03, -3.043788844e+01},
        {5.608128010e+05, -8.371504740e+02, 2.975364532e+00,  1.252249124e-03, -3.740716190e-07, 
             5.936625200e-11, -3.606994100e-15, 0.000000000e+00, 5.339824410e+03, -2.202774769e+00}
    };

	real H_delta_H2;        /* J/mol */
	if(T<1000)
	{
		H_delta_H2= R * T * (
			- Aij_H2[0][0]*pow(T,-2) + Aij_H2[0][1]*pow(T,-1)*log(T) + Aij_H2[0][2]
			+ Aij_H2[0][3]*pow(T,1)/2 + Aij_H2[0][4]*pow(T,2)/3 + Aij_H2[0][5]*pow(T,3)/4 
            + Aij_H2[0][6]*pow(T,4)/5 + Aij_H2[0][8]/T);
	}
	else
	{
		H_delta_H2=R * T * (
			- Aij_H2[1][0]*pow(T,-2) + Aij_H2[1][1]*pow(T,-1)*log(T) + Aij_H2[1][2]
			+ Aij_H2[1][3]*pow(T,1)/2 + Aij_H2[1][4]*pow(T,2)/3 + Aij_H2[1][5]*pow(T,3)/4 
            + Aij_H2[1][6]*pow(T,4)/5 + Aij_H2[1][8]/T);
	}
	return (1e3 * H_delta_H2) / Wt_H2;                     /* J/kg */
}

real Calc_H_Fuel(real T)
{
    real Hg_C2H4 = Calc_H_C2H4(T);
    real Hg_H2 = Calc_H_H2(T);
    return (Hg_C2H4 * MassFraction_C2H4 + Hg_H2 * MassFraction_H2); // J/kg
}

real Calc_H_PE_Add(real T)
{
    return Calc_H_C2H4(T); // PE的焓 J/kg
}

real Calc_H_Paraffin_Add(real T)
{
    real Hg_C2H4 = Calc_H_C2H4(T);
    real Hg_H2 = Calc_H_H2(T);
    return (Hg_C2H4 * (1 - (Wt_H2 / Wt_Paraffin)) + Hg_H2 * (Wt_H2 / Wt_Paraffin)); // J/kg
}

real Calc_Q_PE(real T, real r_pe)
{
    real Hg = Calc_H_C2H4(T); // PE的焓 J/kg
    real Hf_PE = Hf_Fuel_PE_mol / Wt_C2H4; // PE的标准生成焓 J/kg
    return (Hg - Hf_PE) * r_pe * Rho_Fuel_PE; // W/m2
}

real Calc_Delta_H_Paraffin_Lq(real T)
{
    return Cs * (Tm - Ta) + Lm + Cl * (T - Tm); // J/kg
}

real Calc_Delta_H_Paraffin_Lq_Lv(real T)
{
    return Cs * (Tm - Ta) + Lm + Cl * (T - Tm) + Lv; // J/kg
}

real Calc_Q_Paraffin(real T, real r_wax, real r_v)
{
    return (Calc_Delta_H_Paraffin_Lq(T) * r_wax + Lv * r_v) * Rho_Fuel_Paraffin; // W/m2
}

real Calc_Q_Fuel(real T, real r_pe, real r_wax, real r_v)
{
    real Q_PE = Calc_Q_PE(T, r_pe);
    real Q_Paraffin = Calc_Q_Paraffin(T, r_wax, r_v);

    return Q_PE * VolFraction_PE + Q_Paraffin * VolFraction_Paraffin;   // 总热 W/m2
}
