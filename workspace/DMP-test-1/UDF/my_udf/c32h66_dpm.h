#ifndef C32H66_DPM_H
#define C32H66_DPM_H

#include "udf.h"
#include "dpm.h"
#include "surf.h"

#ifndef PI
#define PI 3.14159265359
#endif

#define SURFACE_ZONE_ID 15      // fuel-wall 的 surface id
#define N_FACES 1278            // 面上 face 的数量
#define PARAFFIN_RHO 780.0      // 石蜡液体密度 (kg/m3)

#define D_MIN 0.01e-3              // 石蜡液滴直径范围 (m)
#define D_MAX 1.00e-3              // 石蜡液滴直径范围 (m)

#define Y_OFFSET 0.001e-3        // Y 方向偏移量，调整粒子位置以避免与壁面重合

#define MINIMUM_PARTICLE_MASS 1e-18   /* 用于防止数值上的负质量（可根据量级调小/调大） */
#define MIN_ACTIVE_MASS 1e-20         /* 低于此质量视为消亡 */

#ifndef SPEC_C2H4
/* 请在这里把物种索引替换为你 Fluent case 中的实际索引（从0开始） */
#define SPEC_C2H4  7
#endif

#ifndef SPEC_H2
#define SPEC_H2    5
#endif

#define Zoom_Factor 1.0 // 0.5  /* 用于调整热解速率的放大因子 */

#endif /* C32H66_DPM_H */