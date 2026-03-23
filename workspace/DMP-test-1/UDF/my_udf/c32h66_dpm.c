#include "c32h66_dpm.h"
#include "kinetics.h"
#include "enthalpy.h"

// 避免在函数栈上分配上千个 double 数组。static 变量只初始化一次，避免重复分配内存。
real face_x[N_FACES] = {0};
real face_y[N_FACES] = {0};
// real face_z[N_FACES] = {0}; /* 若 3D 可用，否则留0 */
real face_T[N_FACES] = {0};
real face_mdot[N_FACES] = {0}; /* kg/s, 每个 face 对应的质量注入流（来自 cell UDMI * cell volume） */
real Vx[N_FACES] = {0};
real Vy[N_FACES] = {0};

DEFINE_DPM_INJECTION_INIT(init_paraffin_from_surface, I)
{
    Particle *p;
    face_t f;
    cell_t c;
    Thread *fthread;
    Thread *cthread;

    Domain *d = Get_Domain(1);
    /* 使用 zone id 查找 surface thread（用 zone id 而非 surface id 是常见做法） */
    fthread = Lookup_Thread(d, SURFACE_ZONE_ID);
    // 输出面的名称
    Message("init_paraffin_from_surface: initializing from surface zone id %d, name: %s\n", SURFACE_ZONE_ID, THREAD_NAME(fthread));

    int face_count = 0;

    real centroid[ND_ND];

    Message("init_paraffin_from_surface: initializing arrays for surface zone %d\n", SURFACE_ZONE_ID);

    /* --- 第一次循环：遍历 surface 的 face，把信息逐个存储到数组中 --- */
    begin_f_loop(f, fthread)
    {
        if (face_count >= N_FACES)
        {
            Message("[ERROR] \t init_paraffin_from_surface: WARNING face_count >= N_FACES (%d) - increase N_FACES\n", N_FACES);
            break;
        }

        /* 对应的 cell（face 所接触的 cell，F_C0） */
        c = F_C0(f, fthread);
        cthread = F_C0_THREAD(f, fthread);

        /* face 重心坐标 */
        F_CENTROID(centroid, f, fthread);
        face_x[face_count] = centroid[0];
        face_y[face_count] = (ND_ND > 1 ? (centroid[1]-(Y_OFFSET)) : 0.0);
        // face_z[face_count] = (ND_ND > 2 ? centroid[2] : 0.0);

        /* 读取 cell 中的 UDMI（单位 kg/s） */
        real udmi_val = C_UDMI(c, cthread, 50);
        // real cell_vol = C_VOLUME(c, cthread);
        real mdot_cell = udmi_val;  // * cell_vol; /* kg/s */

        /* 如果该 face 所在 cell 与多个 face 共享（rare），你可能想把 mdot 在相关 faces 间均分。
           这里简化假设每个 face 对应的 cell 的 mdot 全部归到这个 face 上（即一对一映射）。 */
        face_mdot[face_count] = mdot_cell;

        /* 记录 cell 温度以做初始化粒子温度 */
        face_T[face_count] = C_T(c, cthread);    //  F_T(f, fthread);

        Vx[face_count]=C_U(c, cthread);
		Vy[face_count]=C_V(c, cthread);

        face_count++;
    }
    end_f_loop(f, fthread)

    Message("init_paraffin_from_surface: found %d faces from surface zone %d (N_FACES=%d)\n", face_count, SURFACE_ZONE_ID, N_FACES);

    /* 若实际 face 少于 N_FACES 提示 */
    if (face_count < 1)
    {
        Message("init_paraffin_from_surface: no faces found on surface zone %d. Aborting initialization.\n", SURFACE_ZONE_ID);
        return;
    }

    int pp_i = 0;

    /* --- 第二次循环：遍历 injection 的粒子，并把每个粒子分配到对应的 face --- */
    loop(p, I->p)
    {
        if (pp_i >= face_count) 
        {
            /* 如果 injection 中粒子比 face 多，可以两种策略：
             * 1) 按 face 循环复用 (pp_i = pp_i % face_count)
             * 2) 跳出（只初始化前 face_count 个粒子）
             * 这里选择安全的跳出策略，避免越界写入
             */
            Message("init_paraffin_from_surface: reached face_count (%d). Stop assigning more particles.\n", face_count);
            break;
        }

        /* 把粒子位置移动到 face 的重心（可选） */
        PP_POS(p)[0] = face_x[pp_i];
        if (ND_ND > 1) PP_POS(p)[1] = face_y[pp_i];
        // if (ND_ND > 2) PP_POS(p)[2] = face_z[pp_i];

        /* 设定粒子初始温度为该 cell 的温度（或你想要的值） */
        PP_T(p) = face_T[pp_i];

        /* 设置粒子密度为石蜡密度 */
        PP_RHO(p) = PARAFFIN_RHO;

        /* 直径与质量 */

        // 直径在 D_MIN D_MAX 范围内随机分布
        // real rand_frac = ((real)rand()) / ((real)RAND_MAX); /* [0,1] */
        // PP_DIAM(p) = D_MIN + rand_frac * (D_MAX - D_MIN);
        PP_DIAM(p) = 1e-3;
        PP_MASS(p) = PP_RHO(p) * PI * pow(PP_DIAM(p), 3.0) / 6.0;

        /* 赋 flow rate */
        PP_FLOW_RATE(p) = face_mdot[pp_i];

        /* 速度 */
        PP_VEL(p)[0] = Vx[pp_i];
        if (ND_ND > 1) PP_VEL(p)[1] = Vy[pp_i];

        pp_i++;
    }

    Message("init_paraffin_from_surface: injection init finished.\n");
}

/* ---------------- DEFINE_DPM_LAW: 只处理粒子自身（质量、直径、温度） ---------------- */
DEFINE_DPM_LAW(paraffin_pyrolysis_law, tp, coupled)
{
    real T_p = TP_T(tp);
    real dt = TP_DT(tp);
    real mass = TP_MASS(tp);
    real diam = TP_DIAM(tp);
    real rho = (TP_RHO(tp) > 0.0) ? TP_RHO(tp) : PARAFFIN_RHO;

    /* 防御性检查 */
    if (mass <= 0.0 || diam <= 0.0 || dt <= 0.0) 
    {
        ;
    }
    else
    {
        InertHeatingLaw(tp); /* 先调用默认的惰性加热模型处理粒子温度变化 */

        /* 表面积 (m^2) */
        real area = DPM_SURFACE_AREA(diam);

        /* 燃速 (m/s) -> 单个代表粒子的质量损失率 (kg/s) */
        real reg = Paraffin_Evapor_Reg(T_p) * Zoom_Factor; /* 乘以放大因子调整速率 */
        if (!isfinite(reg) || reg < 0.0) reg = 0.0;
        real mp_dot = reg * area * rho;
        if (!isfinite(mp_dot) || mp_dot <= 0.0)
        {
            ;
        }
        else
        {
            /* 计算本步质量减量并更新 */
            real dm = mp_dot * dt;
            if (dm >= mass)
            {
                /* 粒子完全耗尽 */
                TP_MASS(tp) = 0.0;
                TP_DIAM(tp) = 0.0;
                
                tp->stream_index = -1;

                mp_dot = mass; /* 实际损失质量为剩余质量 */
            }
            else
            {
                TP_MASS(tp) = mass - dm;
                TP_DIAM(tp) = DPM_DIAM_FROM_VOL(TP_MASS(tp) / rho);
            }

            /* 能量：如果在 injection 里定义了 latent_heat_ref（J/kg），优先使用 */
            real reaction_heat_per_kg = 0.0;
            // if (TP_INJECTION(tp) != NULL)
            // {
            //     real lh = TP_INJECTION(tp)->latent_heat_ref;
            //     if (lh != 0.0) reaction_heat_per_kg = lh;
            // }
            /* 否则使用 kinetics.h 中的 Lv（你在 kinetics.h 定义的 J/kg） */
            // if (reaction_heat_per_kg == 0.0)
            //     reaction_heat_per_kg = Lv; /* 来自 kinetics.h */

            // if (reaction_heat_per_kg != 0.0)
            // {
            //     /* UpdateTemperature 接受能量速率（J/s）来更新粒子温度（示例） */
            //     UpdateTemperature(tp, -mp_dot * reaction_heat_per_kg, TP_MASS(tp), 1.0);
            // }
        }
    }
}

/* ---------------- DEFINE_DPM_SOURCE: 将粒子损失的质量写回气相（species transport） ----------------
   注意参数顺序必须是 (name, c, t, S, strength, tp)
   S 是 dpms_t*，用于写入 S->species[idx] 和 S->energy（J/s）等
*/
DEFINE_DPM_SOURCE(paraffin_pyrolysis_source, c, t, S, strength, tp)
{
    /* delta_m = (mass lost per particle during its travel through this cell) * strength
       (strength 是粒子流率: particles / s)，得到单位 kg/s (为该 cell 的体积源总质量流量)
    */
    real delta_mass = (TP_MASS0(tp) - TP_MASS(tp)) * strength;

    if (delta_mass > 0.0)
    {
        /* 计算质量分配 */
        const real M_C2H4 = Wt_C2H4;
        const real M_H2   = Wt_H2;
        real wC = 16.0 * M_C2H4;
        real wH = 1.0  * M_H2;
        real sumw = wC + wH;
        real Y_C2H4 = wC / sumw;
        real Y_H2   = wH / sumw;

        /* 边界检查：确保 species 索引合理（避免越界写入） */
        /* 如果你的 SPEC_C2H4 / SPEC_H2 是在头文件中定义的常数，请确认它们与 Fluent 的 species 索引相匹配。 */
        if (SPEC_C2H4 >= 0 && SPEC_H2 >= 0)
        {
            S->species[SPEC_C2H4] += delta_mass * Y_C2H4;
            S->species[SPEC_H2]   += delta_mass * Y_H2;
        }
        else
        {
            Message("paraffin_pyrolysis_source: SPEC indices invalid: C2H4=%d H2=%d\n", SPEC_C2H4, SPEC_H2);
        }

        /* 能量：正确添加（J/s）—— 热解吸热为 Lv (J/kg)，吸热则为 - delta_mass * Lv */
        S->energy -= (delta_mass * Lv);

        /* 推荐：不要直接改写 TP_MASS0(tp)。改成用用户自变量保存上次质量 */
        // /* 如果确实需要标记“已计入”，改用 TP_USER_REAL */
        // TP_MASS0(tp) = TP_MASS(tp); /* 0 号 user-real 用于记录上次质量（确保 injection & law 初始化时设置） */
    }
}


DEFINE_DPM_SWITCH(dpm_switch, tp, coupled)
{
    // cell_t c = TP_CELL(tp);
    // Thread *t = TP_CELL_THREAD(tp);
    // Material *m = TP_MATERIAL(tp); 

    // /* If the relative humidity is higher than 1 
    // * and the particle temperature below the boiling temperature 
    // * switch to condensation law
    // */
    // if ((C_UDMI(c,t,UDM_RH) > 1.0) && (TP_T(tp) < DPM_BOILING_TEMPERATURE(tp, m)))
    //     TP_CURRENT_LAW(tp) = DPM_LAW_USER_1;
    // else
    //     TP_CURRENT_LAW(tp) = DPM_LAW_INITIAL_INERT_HEATING;

    TP_CURRENT_LAW(tp) = DPM_LAW_USER_1;
}

DEFINE_DPM_OUTPUT(filter_and_remove, header, fp, tp, t, plane)
{
    // if (header)
    //     par_fprintf_head(fp, "# Time  X  Y  D  Mass  Temp\n");

    // if (NULLP(tp)) return;

    real mass = TP_MASS(tp);
    // par_fprintf(fp, "%e %e %e %e %e %e\n",
    //             TP_TIME(tp),
    //             TP_POS(tp)[0],
    //             TP_POS(tp)[1],
    //             TP_DIAM(tp),
    //             mass,
    //             TP_T(tp));

    /* 若粒子质量接近0，则删除 */
    if (mass < 1e-18)
        MARK_TP(tp, P_FL_REMOVED);
}

DEFINE_DPM_TIMESTEP(limit_to_e_minus_four,tp,dt)
{
    if (dt > 1.e-3)
    {
        /* TP_NEXT_TIME_STEP(tp) = 1.e-4; */
        return 1.e-3;
    }
    return dt;
} 