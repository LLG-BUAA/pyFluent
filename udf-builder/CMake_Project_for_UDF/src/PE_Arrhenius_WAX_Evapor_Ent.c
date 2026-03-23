#include <malloc.h>
#include "udf.h"
#include "math.h"
#include <stdio.h>
#include <stdlib.h>

/* 包含各个模块的头文件 */
#include "mass_flux_calculator.h"
#include "kinetics.h"
#include "enthalpy.h"
#include "regression.h"
#include "fuel_surface.h"
#include "sources.h"

/* UDM 的预留和重命名 */
#define NUM_UDM 60
static int udm_offset = UDM_UNRESERVED;

DEFINE_EXECUTE_ON_LOADING(rename_udm, libname)
{
    if (udm_offset == UDM_UNRESERVED)
        udm_offset = Reserve_User_Memory_Vars(NUM_UDM);
    if (udm_offset == UDM_UNRESERVED)
    {    Message("You need to define up to %d extra UDMs in GUI and then reload current library %s\n", NUM_UDM, libname);
    // else
    
        Message("%d UDMs have been reserved by the current library %s\n", NUM_UDM, libname);
    }
        /* 重命名各 UDM，下标对应 sources 模块中的设置 */
        Set_User_Memory_Name(0, "udm_SourceFlag");
        Set_User_Memory_Name(1, "udm_ConsTSource");
        Set_User_Memory_Name(2, "udm_flag");
        Set_User_Memory_Name(3, "udm_thk");
        Set_User_Memory_Name(4, "udm_area");
        Set_User_Memory_Name(5, "udm_Titer");
        Set_User_Memory_Name(6, "udm_Ts");
        Set_User_Memory_Name(7, "udm_Tc");
        Set_User_Memory_Name(8, "udm_r");
        Set_User_Memory_Name(9, "udm_Gf");
        Set_User_Memory_Name(10, "udm_Trg");
        Set_User_Memory_Name(11, "udm_k");
        Set_User_Memory_Name(12, "udm_Qtotal");
        Set_User_Memory_Name(13, "udm_Qs");
        Set_User_Memory_Name(14, "udm_Qc4h6");
        Set_User_Memory_Name(15, "udm_Qgflux");
        Set_User_Memory_Name(16, "udm_Qsflux");
        Set_User_Memory_Name(17, "udm_Qsfluent");
        Set_User_Memory_Name(18, "udm_Fuel_Qtsource");
        Set_User_Memory_Name(19, "udm_Paraffing_Qtsource");
        Set_User_Memory_Name(20, "udm_PE_Qtsource");
        Set_User_Memory_Name(21, "udm_CosX");
        Set_User_Memory_Name(22, "udm_CosY");
        Set_User_Memory_Name(23, "udm_CosZ");
        Set_User_Memory_Name(24, "udm_Tsrg");
        Set_User_Memory_Name(25, "udm_Trgerror");
        Set_User_Memory_Name(30, "udm_MassSource");
        Set_User_Memory_Name(31, "udm_XMomSource");
        Set_User_Memory_Name(32, "udm_YMomSource");
        Set_User_Memory_Name(33, "udm_ZMomSource");
        Set_User_Memory_Name(34, "udm_C2H4Source");
        Set_User_Memory_Name(35, "udm_H2Source");
        Set_User_Memory_Name(36, "udm_EnergySourceT");
        
        Set_User_Memory_Name(39, "udm_mdot_at_x");
        Set_User_Memory_Name(40, "udm_rho_at_x");

        Set_User_Memory_Name(43, "udm_mdot_at_x_available");
        Set_User_Memory_Name(45, "udm_GrainPassage_Flag");
        Set_User_Memory_Name(46, "udm_G_f_ent");
        Set_User_Memory_Name(47, "udm_G_f_pe");

        Set_User_Memory_Name(48, "udm_Rho_gas_Set");

        Set_User_Memory_Name(50, "udm_m_dot_ent_DMP");

        Set_User_Memory_Name(51, "udm_r_pe");
        Set_User_Memory_Name(52, "udm_r_wax");
        Set_User_Memory_Name(53, "udm_r_v");
        Set_User_Memory_Name(54, "udm_r_ent");

        Set_User_Memory_Name(58, "udm_volume_fuel_surface");
        Set_User_Memory_Name(59, "udm_D_fuel_surface");
        
    Message("\nUDM Offset for Current Loaded Library = %d\n", udm_offset);
    Message("\n=====================================================\n");
}

DEFINE_GRID_MOTION(Grid_Motion, domain, dt, time, dtime)
{
	Thread *tf = DT_THREAD(dt);
	Thread *tc = THREAD_T0(tf);
	face_t f;
	cell_t c;
	Node *node;
	real dy, x, y, temp;
	real A[ND_ND] = { 0 };
	real average_r = 0, Sum_Area = 0, area = 0;
	int n;

	begin_f_loop(f, tf)
	{
		c = F_C0(f, tf);
		F_AREA(A, f, tf);
		area = NV_MAG(A);
		average_r += area * C_UDMI(c, tc, 8);
		Sum_Area += area;
	}
	end_f_loop(f, tf);
	average_r = average_r / Sum_Area;
	Message("Average Regression Rate=%f\n", average_r);

	/* set deforming flag on adjacent cell zone */
	SET_DEFORMING_THREAD_FLAG(tc);

	/* Update the node position */
	begin_f_loop(f, tf)
	{
		c = F_C0(f, tf);
		dy = C_UDMI(c, tc, 8);
		f_node_loop(f, tf, n)
		{
			node = F_NODE(f, tf, n);
			if (NODE_POS_NEED_UPDATE(node))
			{
				NODE_POS_UPDATED(node);
				x = NODE_X(node);
				y = NODE_Y(node);
				if (y < 14e-3)
				{
					NODE_Y(node) = y + (0.1*temp + 0.9*dy)*dtime;
					temp = (0.1*temp + 0.9*dy);
				}
				else
					NODE_Y(node) = 14e-3;

			}
		}
	}
	end_f_loop(f, tf);
}
