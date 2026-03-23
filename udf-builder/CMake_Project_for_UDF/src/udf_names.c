/* This file generated automatically. */
/*          Do not modify.            */
#include <math.h>
#include "udf.h"
#include "prop.h"
#include "dpm.h"
extern DEFINE_DPM_INJECTION_INIT(init_paraffin_from_surface, I);
extern DEFINE_DPM_LAW(paraffin_pyrolysis_law, tp, coupled);
extern DEFINE_DPM_SOURCE(paraffin_pyrolysis_source, c, t, S, strength, tp);
extern DEFINE_DPM_SWITCH(dpm_switch, tp, coupled);
extern DEFINE_DPM_OUTPUT(filter_and_remove, header, fp, tp, t, plane);
extern DEFINE_DPM_TIMESTEP(limit_to_e_minus_four,tp,dt);
extern DEFINE_PROFILE(fuel_wall_temperature, tf, i);
extern DEFINE_ON_DEMAND(Enable_Ent_Source);
extern DEFINE_ON_DEMAND(Disable_Ent_Source);
extern DEFINE_ON_DEMAND(Fit_Mass_Flow_Function_Fast);
extern DEFINE_ADJUST(Fit_Mass_Flow_Function, domain);
extern DEFINE_ON_DEMAND(Print_Mass_Flow_Function);
extern DEFINE_EXECUTE_ON_LOADING(rename_udm, libname);
extern DEFINE_GRID_MOTION(Grid_Motion, domain, dt, time, dtime);
extern DEFINE_SOURCE(Total_Mass_Source, c, tc, dS, eqn);
extern DEFINE_SOURCE(X_Mom_Source, c, tc, dS, eqn);
extern DEFINE_SOURCE(Y_Mom_Source, c, tc, dS, eqn);
extern DEFINE_SOURCE(Z_Mom_Source, c, tc, dS, eqn);
extern DEFINE_SOURCE(C2H4_Mass_Source, c, tc, dS, eqn);
extern DEFINE_SOURCE(H2_Mass_Source, c, tc, dS, eqn);
extern DEFINE_SOURCE(Energy_Source_t, c, tc, dS, eqn);
extern DEFINE_ON_DEMAND(Non_Source);
extern DEFINE_ON_DEMAND(Vari_Source);
extern DEFINE_ON_DEMAND(Constan_Sources);
extern DEFINE_ON_DEMAND(Cal_Rho_Gas);
extern DEFINE_ON_DEMAND(set_r_to);
__declspec(dllexport) UDF_Data udf_data[] = {
{"init_paraffin_from_surface", (void (*)(void))init_paraffin_from_surface, UDF_TYPE_DPM_INJECTION_INIT},
{"paraffin_pyrolysis_law", (void (*)(void))paraffin_pyrolysis_law, UDF_TYPE_DPM_LAW},
{"paraffin_pyrolysis_source", (void (*)(void))paraffin_pyrolysis_source, UDF_TYPE_DPM_SOURCE},
{"dpm_switch", (void (*)(void))dpm_switch, UDF_TYPE_DPM_SWITCH},
{"filter_and_remove", (void (*)(void))filter_and_remove, UDF_TYPE_DPM_OUTPUT},
{"limit_to_e_minus_four", (void (*)(void))limit_to_e_minus_four, UDF_TYPE_DPM_TIMESTEP},
{"fuel_wall_temperature", (void (*)(void))fuel_wall_temperature, UDF_TYPE_PROFILE},
{"Enable_Ent_Source", (void (*)(void))Enable_Ent_Source, UDF_TYPE_ON_DEMAND},
{"Disable_Ent_Source", (void (*)(void))Disable_Ent_Source, UDF_TYPE_ON_DEMAND},
{"Fit_Mass_Flow_Function_Fast", (void (*)(void))Fit_Mass_Flow_Function_Fast, UDF_TYPE_ON_DEMAND},
{"Fit_Mass_Flow_Function", (void (*)(void))Fit_Mass_Flow_Function, UDF_TYPE_ADJUST},
{"Print_Mass_Flow_Function", (void (*)(void))Print_Mass_Flow_Function, UDF_TYPE_ON_DEMAND},
{"rename_udm", (void (*)(void))rename_udm, UDF_TYPE_EXECUTE_ON_LOADING},
{"Grid_Motion", (void (*)(void))Grid_Motion, UDF_TYPE_GRID_MOTION},
{"Total_Mass_Source", (void (*)(void))Total_Mass_Source, UDF_TYPE_SOURCE},
{"X_Mom_Source", (void (*)(void))X_Mom_Source, UDF_TYPE_SOURCE},
{"Y_Mom_Source", (void (*)(void))Y_Mom_Source, UDF_TYPE_SOURCE},
{"Z_Mom_Source", (void (*)(void))Z_Mom_Source, UDF_TYPE_SOURCE},
{"C2H4_Mass_Source", (void (*)(void))C2H4_Mass_Source, UDF_TYPE_SOURCE},
{"H2_Mass_Source", (void (*)(void))H2_Mass_Source, UDF_TYPE_SOURCE},
{"Energy_Source_t", (void (*)(void))Energy_Source_t, UDF_TYPE_SOURCE},
{"Non_Source", (void (*)(void))Non_Source, UDF_TYPE_ON_DEMAND},
{"Vari_Source", (void (*)(void))Vari_Source, UDF_TYPE_ON_DEMAND},
{"Constan_Sources", (void (*)(void))Constan_Sources, UDF_TYPE_ON_DEMAND},
{"Cal_Rho_Gas", (void (*)(void))Cal_Rho_Gas, UDF_TYPE_ON_DEMAND},
{"set_r_to", (void (*)(void))set_r_to, UDF_TYPE_ON_DEMAND},
};
__declspec(dllexport) int n_udf_data = sizeof(udf_data)/sizeof(UDF_Data);
#include "version.h"
__declspec(dllexport) void UDF_Inquire_Release(int *major, int *minor, int *revision)
{
	*major = RampantReleaseMajor;
	*minor = RampantReleaseMinor;
	*revision = RampantReleaseRevision;
}