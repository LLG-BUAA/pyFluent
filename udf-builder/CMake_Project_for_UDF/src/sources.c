#include "sources.h"
#include "mass_flux_calculator.h"
#include "fuel_surface.h"
#include "kinetics.h"

/* 总质量源项 */
DEFINE_SOURCE(Total_Mass_Source, c, tc, dS, eqn)
{
    real Ent_Add_Source = 0.0;
    real Vap_Add_Source = 0.0;

    if (C_UDMI(c,tc,45) > 0.975)
    {
        Ent_Add_Source = (4.0 * C_UDMI(c,tc,46) / D);
    }
    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            Vap_Add_Source = 5e-4 * Rho_Fuel / 1.0e-5;
        else
            Vap_Add_Source = (C_UDMI(c,tc,9) - C_UDMI(c,tc,46)) / C_UDMI(c,tc,3);
    }

    C_UDMI(c,tc,30) = Ent_Add_Source + Vap_Add_Source;
    dS[eqn] = 0;

    return C_UDMI(c,tc,30);
}

/* X 动量源项 */
DEFINE_SOURCE(X_Mom_Source, c, tc, dS, eqn)
{
    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            C_UDMI(c,tc,31) = - pow(Rho_Fuel,2) * pow(5e-4,2) / 5 / 1.0e-5;
        else
            C_UDMI(c,tc,31) = - C_UDMI(c,tc,9) * C_UDMI(c,tc,9) / C_R(c,tc) / C_UDMI(c,tc,3) * C_UDMI(c,tc,21);
        dS[eqn]=0;
        return C_UDMI(c,tc,31);
    }
    return 0;
}

/* Y 动量源项 */
DEFINE_SOURCE(Y_Mom_Source, c, tc, dS, eqn)
{
    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            C_UDMI(c,tc,32) = -pow(Rho_Fuel,2)*pow(5e-4,2)/5/1.0e-5;
        else
            C_UDMI(c,tc,32) = - Rho_Fuel * C_UDMI(c,tc,8) * Rho_Fuel * C_UDMI(c,tc,8) / C_R(c,tc) / C_UDMI(c,tc,3) * C_UDMI(c,tc,22);
        dS[eqn]=0;
        return C_UDMI(c,tc,32);
    }
    return 0;
}

/* Z 动量源项 */
DEFINE_SOURCE(Z_Mom_Source, c, tc, dS, eqn)
{
    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            C_UDMI(c,tc,33) = -pow(Rho_Fuel,2)*pow(5e-4,2)/5/1.0e-5;
        else
            C_UDMI(c,tc,33) = - C_UDMI(c,tc,9) * C_UDMI(c,tc,9) / C_R(c,tc) / C_UDMI(c,tc,3) * C_UDMI(c,tc,23);
        dS[eqn]=0;
        return C_UDMI(c,tc,33);
    }
    return 0;
}

/* C2H4 组分源项 */
DEFINE_SOURCE(C2H4_Mass_Source, c, tc, dS, eqn)
{
    real Ent_Add_Source = 0.0;
    real Vap_Add_Source = 0.0;
    
    if (C_UDMI(c,tc,45) > 0.975)
    {
        Ent_Add_Source = (4.0 * C_UDMI(c,tc,46) / D) * (1 - (Wt_H2 / Wt_Paraffin));
    }
    
    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            Vap_Add_Source = 5e-4 * Rho_Fuel / 1.0e-5;
        else
            Vap_Add_Source = ((C_UDMI(c,tc,9) - C_UDMI(c,tc,46)) * MassFraction_C2H4) / C_UDMI(c,tc,3);
    }
    
    C_UDMI(c,tc,34) = (Vap_Add_Source + Ent_Add_Source);
    dS[eqn] = 0;
    return C_UDMI(c,tc,34);
}

/* H2 组分源项 */
DEFINE_SOURCE(H2_Mass_Source, c, tc, dS, eqn)
{
    real Ent_Add_Source = 0.0;
    real Vap_Add_Source = 0.0;

    if (C_UDMI(c,tc,45) > 0.975)
    {
        Ent_Add_Source = (4.0 * C_UDMI(c,tc,46) / D) * (Wt_H2 / Wt_Paraffin);
    }

    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            Vap_Add_Source = 5e-4 * Rho_Fuel / 1.0e-5;
        else
            Vap_Add_Source = ((C_UDMI(c,tc,9) - C_UDMI(c,tc,46)) - C_UDMI(c,tc,47)) * (Wt_H2 / Wt_Paraffin) / C_UDMI(c,tc,3);//
    }
    
    C_UDMI(c,tc,35) = (Vap_Add_Source + Ent_Add_Source);
    dS[eqn] = 0;
    return C_UDMI(c,tc,35);
}

/* 能量源项 */
DEFINE_SOURCE(Energy_Source_t, c, tc, dS, eqn)
{
    real Ent_Add_Source = 0.0;
    real Vap_Add_Source = 0.0;
    
    if (C_UDMI(c,tc,45) > 0.975)
    {
        Ent_Add_Source = (4.0 * C_UDMI(c,tc,46) / D) * (-1.0 * Lv + C_UDMI(c,tc,19));
    }
    if (C_UDMI(c,tc,0) > 0.9)
    {
        if (C_UDMI(c,tc,1) < 0.5)
            Vap_Add_Source = 5e-4 * Rho_Fuel * Calc_H_C2H4(900) / 1.0e-5;
        else
            Vap_Add_Source = (C_UDMI(c,tc,47) * C_UDMI(c,tc,20) + (C_UDMI(c,tc,9) - C_UDMI(c,tc,47)) * C_UDMI(c,tc,19) + C_UDMI(c,tc,46) * (C_UDMI(c,tc,19) - Lv)) / C_UDMI(c,tc,3);
    }

    C_UDMI(c,tc,36) = Ent_Add_Source + Vap_Add_Source;
    dS[eqn] = 0;
    return C_UDMI(c,tc,36);
}

/* 以下 on-demand UDF 控制不同源项 */
DEFINE_ON_DEMAND(Non_Source)
{
    Domain *d;
    Thread *t;
    cell_t c;
    d = Get_Domain(1);
    thread_loop_c(t, d)
    {
        begin_c_loop(c, t)
        {
            C_UDMI(c, t, 0) = 0;
        }
        end_c_loop(c, t)
    }
    Message("\n NO Sources Used");
}

DEFINE_ON_DEMAND(Vari_Source)
{
    Domain *d;
    Thread *t;
    cell_t c;
    d = Get_Domain(1);
    thread_loop_c(t, d)
    {
        begin_c_loop(c, t)
        {
            C_UDMI(c, t, 1) = 1;
            C_UDMI(c, t, 43) = 0; /* 标记当前 cell 质量流量不可用 */
        }
        end_c_loop(c, t)
    }
    Message("\n Variable Sources Used");
}

DEFINE_ON_DEMAND(Constan_Sources)
{
    Domain *d;
    Thread *t;
    cell_t c;
    d = Get_Domain(1);
    thread_loop_c(t, d)
    {
        begin_c_loop(c, t)
        {
            C_UDMI(c, t, 1) = 0;
        }
        end_c_loop(c, t)
    }
    Message("\n Constant Sources Used");
}

DEFINE_ON_DEMAND(Cal_Rho_Gas)
{
    Domain *d;
    Thread *t;
    cell_t c;
    d = Get_Domain(1);

    real n = 0;
    real mass_all = 0;
    real rho_all = 0;
    real v_all = 0;
    real rho_avg = 0;
    
    thread_loop_c(t, d)
    {
        begin_c_loop(c, t)
        {
            if (C_UDMI(c, t, 43) > 0.95)
            {
                if (C_UDMI(c, t, 40) > 0.1){
                    // mass_all += C_UDMI(c, t, 40) * C_VOLUME(c, t);
                    // v_all += C_VOLUME(c, t);
                    rho_all += C_UDMI(c, t, 40);
                    n += 1;
                }
            }
        }
        end_c_loop(c, t)
    }

    // rho_avg = mass_all / v_all;
    rho_avg = rho_all / n;

    Message("\n Rho_avg: %f", rho_avg);
}

DEFINE_ON_DEMAND(set_r_to)
{
    Domain *d;
    Thread *t;
    cell_t c;
    d = Get_Domain(1);
    thread_loop_c(t, d)
    {
        begin_c_loop(c, t)
        {
            C_UDMI(c, t, 8) = 0.1e-3; /* 标记当前 cell 质量流量不可用 */
        }
        end_c_loop(c, t)
    }
    Message("\n Variable Sources Used");
}