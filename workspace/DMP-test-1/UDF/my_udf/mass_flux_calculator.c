#include "mass_flux_calculator.h"
#include "udf.h"
#include "fuel_surface.h"
#include "kinetics.h"
#include "regression.h"
#include "enthalpy.h"
#include <math.h>
#include <stdio.h>


/* ======= 配置参数 ======= */
#define REPORT_NAME "report-def-m-dot-inside-fuel"
#define X_START 25.0
#define X_END   175.0
#define POLY_ORDER 6
#define N_VALUES 7
#define EPS_SMALL 1e-12

/* ======= 全局变量 ======= */
real coeffs[POLY_ORDER + 1] = {0.0};
static int fitted = 0;   /* 是否已拟合 */
int first_output = 1;

/* 预计算x坐标（等距） */
static const real x_fixed[N_VALUES] = {
    25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0
};

/* ======= 最小二乘多项式拟合（固定大小优化版） ======= */
void polynomial_fit_fast(const real *x, const real *y, int n, int order, real *coeff)
{
    const int m = order + 1;
    real X[2 * POLY_ORDER + 1] = {0};
    real B[POLY_ORDER + 1];
    real A[POLY_ORDER + 1][POLY_ORDER + 2];
    int i, j, k;

    /* 计算各阶次幂和 */
    for (i = 0; i <= 2 * order; i++)
    {
        X[i] = 0.0;
        for (j = 0; j < n; j++)
            X[i] += pow(x[j], i);
    }

    /* 构建正规方程组 A|B */
    for (i = 0; i <= order; i++)
    {
        for (j = 0; j <= order; j++)
            A[i][j] = X[i + j];

        B[i] = 0.0;
        for (j = 0; j < n; j++)
            B[i] += pow(x[j], i) * y[j];
        A[i][m] = B[i];
    }

    /* 高斯消元 */
    for (i = 0; i < m - 1; i++)
    {
        for (k = i + 1; k < m; k++)
        {
            real t = A[k][i] / (A[i][i] + EPS_SMALL);
            for (j = 0; j <= m; j++)
                A[k][j] -= t * A[i][j];
        }
    }

    /* 回代求解 */
    for (i = m - 1; i >= 0; i--)
    {
        coeff[i] = A[i][m];
        for (j = i + 1; j < m; j++)
            coeff[i] -= A[i][j] * coeff[j];
        coeff[i] /= (A[i][i] + EPS_SMALL);
    }
}

/* ======= 拟合质量流率函数（轻量版） ======= */
void fit_mass_flow_function()
{
    int rv, index;
    real values[N_VALUES];
    int ids[N_VALUES];

    /* 获取报告值 */
    rv = Get_Report_Definition_Values(REPORT_NAME, 0, NULL, values, ids, &index);
    if (rv != 0)
    {
        Message("Failed to read report definition: %s\n", REPORT_NAME);
        return;
    }

    // Message("Report definition values retrieved successfully.\n Values:\n");
    // for (int i = 0; i < N_VALUES; i++)
    //     Message("--> x = %.2f mm, m_dot = %.6e kg/s\n", x_fixed[i], values[i]);

    // values[0] < EPS_SMALL || 

    if (values[0] > 1e6 || isnan(values[0]))
    {
        Message("Report values are not valid for fitting.\n");
        // 所有values设为15e-3
        for (int i = 0; i < N_VALUES; i++)
            values[i] = 0.005;
    }

    /* 执行拟合 */
    polynomial_fit_fast(x_fixed, values, N_VALUES, POLY_ORDER, coeffs);

    fitted = 1;

    /* 简洁输出（仅首次） */
    if (first_output)
    {
        // 输出rv结果
        Message("Report values retrieved successfully: %d\n", rv);
        for (int i = 0; i < N_VALUES; i++)
        {
            Message("x = %.2f mm, m_dot = %.6e kg/s\n", x_fixed[i], values[i]);
        }

        Message("\n=== Mass Flow Polynomial Fit Initialized ===\n");
        Message("Report: %s | Points: %d | Order: %d\n", REPORT_NAME, N_VALUES, POLY_ORDER);
        Message("Iteration index: %d\n", index);
        for (int i = 0; i <= POLY_ORDER; i++)
            Message("Coeff[%d] = %.6e\n", i, coeffs[i]);
        Message("============================================\n\n");
        first_output = 0;
    }
}

/* ======= 计算指定位置质量流率 ======= */
real cal_m_dot_x_use_fit_function(real x)
{
    if (!fitted)
    {
        Message("Polynomial not fitted yet.\n");
        return 0.0;
    }

    real y = 0.0;
    for (int i = 0; i <= POLY_ORDER; i++)
        y += coeffs[i] * pow(x, i);
    return y;
}

/* ======= 手动触发命令：测试用 ======= */
DEFINE_ON_DEMAND(Fit_Mass_Flow_Function_Fast)
{
    first_output = 1; // 强制输出
    fit_mass_flow_function();
    real xtest = 100.0;
    real ytest = cal_m_dot_x_use_fit_function(xtest);
    Message("m_dot(%.1f mm) = %.6e kg/s\n", xtest, ytest);
}

DEFINE_ADJUST(Fit_Mass_Flow_Function, domain)
{
    fit_mass_flow_function();
}

DEFINE_ON_DEMAND(Print_Mass_Flow_Function)
{
    first_output = 1; // 强制输出

    Message("\n=== Mass Flow Polynomial Coefficients ===\n");
    for (int i = 0; i <= POLY_ORDER; i++)
        Message("Coeff[%d] = %.6e\n", i, coeffs[i]);
    Message("=========================================\n\n");

    real xtest = 100.0;
    real ytest = cal_m_dot_x_use_fit_function(xtest);
    Message("m_dot(%.1f mm) = %.6e kg/s\n", xtest, ytest);
}

// ------------------------------------------------------------------------------



/* 调试相关的全局设置，若 debug_flag 为 0 则不输出调试信息 */
static int debug_flag   = 0;       /* 调试开关，1 表示开启调试信息输出 */
static real debug_target = 0.04;   /* 目标截面位置 */
static real debug_tol    = 0.001;   /* 目标截面误差 */

/* 计算二维面法向量，采用旋转90度 (-dy, dx) 的方法 */
void compute_face_normal(face_t f, Thread *tf, real normal[ND_ND])
{
    Node *node0 = F_NODE(f, tf, 0);
    Node *node1 = F_NODE(f, tf, 1);
    real x0 = NODE_X(node0), y0 = NODE_Y(node0);
    real x1 = NODE_X(node1), y1 = NODE_Y(node1);
    real dx = x1 - x0;
    real dy = y1 - y0;
    real mag = sqrt(dx*dx + dy*dy);
    if (mag < TOL)
    {
        normal[0] = normal[1] = normal[2] = 0.0;
        return;
    }
    normal[0] = -dy / mag;
    normal[1] = dx / mag;
    normal[2] = 0.0;
}

/* 计算给定 cell 截面总质量流量 */
real Calc_Mdot_At_Cell(cell_t c, Thread *tc)
{
    C_UDMI(c, tc, 43) = 1;  /* 标记当前 cell 质量流量可用 */

    real tol = TOL;
    real x_target = 0.0;
    int n_nodes = C_NNODES(c, tc);
    real min_x = 1e30;
    
    /* 遍历 cell 内所有节点，选取 x 坐标最小的节点（作为左侧边界） */
    int i;
    for (i = 0; i < n_nodes; i++)
    {
        Node *node = C_NODE(c, tc, i);
        real node_x = NODE_X(node);
        if (node_x < min_x)
        {
            min_x = node_x;
            x_target = node_x;
        }
    }
    
    /* 若调试开关开启且 x_target 在目标截面附近，则打印调试信息 */
    if (debug_flag && fabs(x_target - debug_target) < debug_tol)
    {           
        Message("\n------------------------------------------------------------------------------\n");
        Message("-> x_target: %f\n", x_target);
    }

    real total_rho = 0.0;
    int n_faces = 0;

    real total_mass_flow = 0.0;
    Domain *domain = Get_Domain(1);
    
    Thread *tf;
    thread_loop_f(tf, domain)
    {
        face_t f;
        begin_f_loop(f, tf)
        {
            /* 计算面心坐标，判断其 x 坐标是否处于目标截面附近 */
            real face_centroid[ND_ND];
            F_CENTROID(face_centroid, f, tf);
            real delta_x = face_centroid[0] - x_target;
            if (delta_x > -tol*10 && delta_x < tol*50)
            {
                /* 计算面法向，仅处理法向主要沿 x 轴的面 */
                real normal[ND_ND];
                compute_face_normal(f, tf, normal);
                if (fabs(normal[0]) > 0.9)
                {
                    real flux = F_FLUX(f, tf);
                    /* 保证流量正方向为 x 正方向：当法向 x 分量为正时，对流率取负 */
                    if (normal[0] > 0.0)
                        flux = -flux;
                    /* 单位转换：流率乘以 2π，单位为 kg/s */
                    flux = flux * 2 * PI;
                    total_mass_flow += flux;
                    
                    /* 若调试开关开启，则输出面信息 */
                    if (debug_flag && fabs(x_target - debug_target) < debug_tol)
                    {                
                        Node *node0 = F_NODE(f, tf, 0);
                        Node *node1 = F_NODE(f, tf, 1);
                        real y0 = NODE_Y(node0);
                        real y1 = NODE_Y(node1);
                        Message("\t-> (%.4f, %.4f): [%.4f - %.4f],\tnormal: (%.4f, %.4f),\tflux: %.4f\n",
                                face_centroid[0]*1e3, face_centroid[1]*1e3,
                                y0*1e3, y1*1e3, normal[0], normal[1], flux);
                    }
                    
                    if (face_centroid[0] > 0.0250001)
                    {
                        /* 获取当前面所在下游cell */
                        cell_t c_now;
                        Thread *tc_now;

                        c_now = F_C0(f, tf);
                        tc_now = F_C0_THREAD(f, tf);
                        
                        total_rho += C_R(c_now, tc_now);
                        n_faces++; 

                        C_UDMI(c_now, tc_now, 45) = 1;                  /* 标记药柱通道单元 */
                        C_UDMI(c_now, tc_now, 46) = 0.00; // C_UDMI(c, tc, 46);
                        C_UDMI(c_now, tc_now, 19) = Calc_H_Paraffin_Add(C_UDMI(c, tc, 5)); /* 存储当前截面石蜡焓值 */
                    }     
                }          
            }
        }
        end_f_loop(f, tf)
    }

    if (total_mass_flow < 1e-4)
    {
        // C_UDMI(c, tc, 43) = 0;  /* 标记当前 cell 质量流量不可用 */
        // Message("Error: Total mass flow is not available.\n");
        Message("Error: Total mass flow is not available.\n");
        return 0.0150;
    }

    C_UDMI(c, tc, 39) = total_mass_flow;        /* 存储当前截面质量流量 mdot_at_x */
    
    C_UDMI(c, tc, 40) = total_rho / n_faces;    /* 存储当前截面平均密度 rho_at_x */

    return total_mass_flow;
}
