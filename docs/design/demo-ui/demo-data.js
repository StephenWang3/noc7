// 由 build_demo_data.py 生成，数据全部来自 fixtures/ 的合成工单包。不要手改。
window.NOC7_DEMO = {
 "element_labels": {
  "start_time": "发生时间",
  "end_time": "结束时间",
  "phenomenon": "故障现象",
  "responsible_party": "故障责任方",
  "cause": "故障原因",
  "handling_process": "处理过程",
  "location": "故障地点"
 },
 "tickets": [
  {
   "ticket": {
    "ticket_ref": "SYN-P04",
    "title": "【合成】道路施工挖断光缆致专线中断",
    "category": "业务中断",
    "list_status": "已结单",
    "data_class": "synthetic",
    "captured": "2026-10-11T11:30:00+08:00"
   },
   "downloads": {
    "docx": "samples/SYN-P04-company-report.docx",
    "html": "samples/SYN-P04-company-report.html"
   },
   "analysis": {
    "schema_version": "1.0",
    "ticket_ref": "SYN-P04",
    "data_class": "synthetic",
    "data_cutoff": "2026-10-11T11:30:00+08:00",
    "run": {
     "provider": "rules",
     "rules_version": "1.2",
     "prompt_version": null,
     "finished_at": "2026-10-29T04:53:45.916892+00:00"
    },
    "materials": [
     {
      "id": "M01",
      "kind": "ticket_fields",
      "path": "ticket.json",
      "parse_status": "parsed"
     },
     {
      "id": "M02",
      "kind": "process_log",
      "path": "process_log.json",
      "parse_status": "parsed"
     },
     {
      "id": "M03",
      "kind": "pdf",
      "path": "attachments/M03-repair-report.pdf",
      "parse_status": "parsed"
     }
    ],
    "evidence": [
     {
      "id": "M01/f:ticket_no",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "ticket_no"
      },
      "text": "SYN-P04"
     },
     {
      "id": "M01/f:customer",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "customer"
      },
      "text": "示例客户壬（合成）"
     },
     {
      "id": "M01/f:circuit_id",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "circuit_id"
      },
      "text": "SYN-CKT-1024"
     },
     {
      "id": "M01/f:created_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "created_at"
      },
      "text": "2026-10-10 15:50:08"
     },
     {
      "id": "M01/f:fault_type",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "fault_type"
      },
      "text": "业务中断"
     },
     {
      "id": "M01/f:occurred_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "occurred_at"
      },
      "text": "2026-10-10 15:42:00"
     },
     {
      "id": "M01/f:recovered_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "recovered_at"
      },
      "text": "2026-10-10 19:08:00"
     },
     {
      "id": "M01/f:duration_returned",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "duration_returned"
      },
      "text": "206分钟"
     },
     {
      "id": "M01/f:description",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "description"
      },
      "text": "客户报专线 SYN-CKT-1024 业务中断。"
     },
     {
      "id": "M01/f:cause",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "cause"
      },
      "text": "市政道路施工挖断 24 芯光缆，已熔接恢复。"
     },
     {
      "id": "M01/f:responsible_party",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "responsible_party"
      },
      "text": "第三方施工单位：示例建设公司（合成）"
     },
     {
      "id": "M02/log:1",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 1
      },
      "text": "客户来电报障建单。"
     },
     {
      "id": "M02/log:2",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 2
      },
      "text": "已受理。"
     },
     {
      "id": "M02/log:3",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 3
      },
      "text": "查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。"
     },
     {
      "id": "M02/log:4",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 4
      },
      "text": "派线路维护部现场抢修。"
     },
     {
      "id": "M02/log:5",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 5
      },
      "text": "现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。"
     },
     {
      "id": "M02/log:6",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 6
      },
      "text": "18:55 熔接完成。"
     },
     {
      "id": "M02/log:7",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 7
      },
      "text": "19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。"
     },
     {
      "id": "M02/log:8",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 8
      },
      "text": "返单。"
     },
     {
      "id": "M02/log:9",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 9
      },
      "text": "上传现场抢修报告（PDF）。"
     },
     {
      "id": "M02/log:10",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 10
      },
      "text": "责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。"
     },
     {
      "id": "M02/log:11",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 11
      },
      "text": "结单。"
     },
     {
      "id": "M03/p1:b0",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        54.0,
        240.0,
        75.5999984741211
       ]
      },
      "text": "现场抢修报告（合成）"
     },
     {
      "id": "M03/p1:b1",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        97.0,
        379.0,
        110.19999694824219
       ]
      },
      "text": "工单：SYN-P04    电路：SYN-CKT-1024"
     },
     {
      "id": "M03/p1:b2",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        119.0,
        445.0,
        132.1999969482422
       ]
      },
      "text": "报告人：线路工程师AG（线路维护部）    日期：2026-10-10"
     },
     {
      "id": "M03/p1:b3",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        161.0,
        138.0,
        176.60000610351562
       ]
      },
      "text": "一、故障概况"
     },
     {
      "id": "M03/p1:b4",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        189.0,
        368.0,
        202.1999969482422
       ]
      },
      "text": "告警时间：2026-10-10 15:42（R_LOS）"
     },
     {
      "id": "M03/p1:b5",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        211.0,
        478.0,
        224.1999969482422
       ]
      },
      "text": "故障点：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m"
     },
     {
      "id": "M03/p1:b6",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        233.0,
        313.0,
        246.1999969482422
       ]
      },
      "text": "OTDR 测距：距 A 端局站 3.21 km"
     },
     {
      "id": "M03/p1:b7",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        255.0,
        401.0,
        268.20001220703125
       ]
      },
      "text": "故障原因：市政道路施工（示例建设公司，合成）挖断 24 芯光缆"
     },
     {
      "id": "M03/p1:b8",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        297.0,
        138.0,
        312.6000061035156
       ]
      },
      "text": "二、抢修经过"
     },
     {
      "id": "M03/p1:b9",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        325.0,
        269.0,
        338.20001220703125
       ]
      },
      "text": "16:40 到达现场，确认光缆被挖断；"
     },
     {
      "id": "M03/p1:b10",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        347.0,
        247.0,
        360.20001220703125
       ]
      },
      "text": "17:10 施工方停工，开挖保护；"
     },
     {
      "id": "M03/p1:b11",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        369.0,
        390.0,
        382.20001220703125
       ]
      },
      "text": "18:55 24 芯熔接完成，平均熔接损耗 0.03 dB；"
     },
     {
      "id": "M03/p1:b12",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 1,
       "bbox": [
        60.0,
        391.0,
        280.0,
        404.20001220703125
       ]
      },
      "text": "19:08 网管确认告警清除，业务恢复。"
     },
     {
      "id": "M03/p2:b0",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 2,
       "bbox": [
        60.0,
        59.0,
        164.0,
        74.5999984741211
       ]
      },
      "text": "三、现场照片说明"
     },
     {
      "id": "M03/p2:b1",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 2,
       "bbox": [
        60.0,
        87.0,
        379.0,
        100.19999694824219
       ]
      },
      "text": "照片 1：人井 SYN-MH-0102 东侧开挖现场（略）"
     },
     {
      "id": "M03/p2:b2",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 2,
       "bbox": [
        60.0,
        109.0,
        225.0,
        122.19999694824219
       ]
      },
      "text": "照片 2：熔接盒封装完成（略）"
     },
     {
      "id": "M03/p2:b3",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "page",
       "page": 2,
       "bbox": [
        60.0,
        153.0,
        225.0,
        166.1999969482422
       ]
      },
      "text": "现场负责人签字：线路工程师AG"
     }
    ],
    "elements": {
     "start_time": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:occurred_at"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-10-10 15:42:00",
       "iso": "2026-10-10T15:42:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C2",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:created_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-10 15:50:08",
         "iso": "2026-10-10T15:50:08+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:occurred_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-10 15:42:00",
         "iso": "2026-10-10T15:42:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "fault_start_field"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-10 15:50:08",
         "iso": "2026-10-10T15:50:08+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:3",
         "M01/f:occurred_at"
        ],
        "attribution": "noc_check",
        "note": "原文只有时刻；日期与同单对应起止字段对齐，保留两处依据。",
        "time": {
         "raw": "15:42",
         "iso": "2026-10-10T15:42:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "alarm_raised"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M03/p1:b4"
        ],
        "attribution": "field_engineer",
        "time": {
         "raw": "2026-10-10 15:42",
         "iso": "2026-10-10T15:42:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "alarm_raised"
       }
      ]
     },
     "end_time": {
      "status": "confirmed",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:7"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-10-10 19:08:00",
       "iso": "2026-10-10T19:08:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C1",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:recovered_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-10 19:08:00",
         "iso": "2026-10-10T19:08:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "recovery_field"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "18:55",
         "iso": "2026-10-10T18:55:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "repair_completed"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "19:08",
         "iso": "2026-10-10T19:08:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "alarm_cleared"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "note": "客户确认时刻，仅表示此时已正常，不替代实际恢复时刻。",
        "time": {
         "raw": "19:15",
         "iso": "2026-10-10T19:15:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "customer_confirmed_recovery"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-10 19:18:00",
         "iso": "2026-10-10T19:18:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_returned"
       },
       {
        "id": "C6",
        "evidence_refs": [
         "M02/log:11"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-11 11:00:00",
         "iso": "2026-10-11T11:00:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       }
      ]
     },
     "phenomenon": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:description",
       "M02/log:3",
       "M02/log:7",
       "M03/p1:b4",
       "M03/p1:b12"
      ],
      "issues": [],
      "value": "客户反馈：客户报专线 SYN-CKT-1024 业务中断。；检查显示：查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。；检查显示：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。；现场工程师称：告警时间：2026-10-10 15:42（R_LOS）；现场工程师称：19:08 网管确认告警清除，业务恢复。",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "description": "客户报专线 SYN-CKT-1024 业务中断。",
        "metric": "告警/状态",
        "scope": "客户报专线 SYN-CKT-1024 业务中断。"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。",
        "metric": "告警/状态",
        "scope": "查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "description": "19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。",
        "metric": "告警/状态",
        "scope": "19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M03/p1:b4"
        ],
        "attribution": "field_engineer",
        "description": "告警时间：2026-10-10 15:42（R_LOS）",
        "metric": "告警/状态",
        "scope": "告警时间：2026-10-10 15:42（R_LOS）"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M03/p1:b12"
        ],
        "attribution": "field_engineer",
        "description": "19:08 网管确认告警清除，业务恢复。",
        "metric": "告警/状态",
        "scope": "19:08 网管确认告警清除，业务恢复。"
       }
      ]
     },
     "responsible_party": {
      "status": "confirmed",
      "evidence_refs": [
       "M02/log:10"
      ],
      "issues": [],
      "value": "责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。",
      "selected": "C2",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:responsible_party"
        ],
        "attribution": "system_field",
        "party": "第三方施工单位：示例建设公司（合成）",
        "basis": "claimed"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "noc_check",
        "party": "责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。",
        "basis": "formal_determination"
       }
      ]
     },
     "cause": {
      "status": "confirmed",
      "evidence_refs": [
       "M02/log:5"
      ],
      "issues": [],
      "value": "现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。",
      "selected": "C2",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "statement": "市政道路施工挖断 24 芯光缆，已熔接恢复。",
        "cause_kind": "root_cause_claimed"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "field_engineer",
        "statement": "现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。",
        "cause_kind": "root_cause_confirmed"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M03/p1:b7"
        ],
        "attribution": "field_engineer",
        "statement": "故障原因：市政道路施工（示例建设公司，合成）挖断 24 芯光缆",
        "cause_kind": "root_cause_claimed"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M03/p1:b9"
        ],
        "attribution": "field_engineer",
        "statement": "16:40 到达现场，确认光缆被挖断；",
        "cause_kind": "root_cause_claimed"
       }
      ]
     },
     "handling_process": {
      "status": "documented",
      "evidence_refs": [
       "M02/log:1",
       "M02/log:2",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5",
       "M02/log:6",
       "M02/log:7",
       "M02/log:8",
       "M02/log:9",
       "M02/log:10",
       "M02/log:11"
      ],
      "issues": [],
      "value": [
       {
        "id": "P1",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-10-10 15:50:08",
         "iso": "2026-10-10T15:50:08+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "系统",
        "action": "客户来电报障建单。",
        "step_kind": "workflow"
       },
       {
        "id": "P2",
        "evidence_refs": [
         "M02/log:2"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 15:52:30",
         "iso": "2026-10-10T15:52:30+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员AF",
        "action": "已受理。",
        "step_kind": "workflow"
       },
       {
        "id": "P3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 15:58:14",
         "iso": "2026-10-10T15:58:14+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员AF",
        "action": "查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。",
        "step_kind": "check_result"
       },
       {
        "id": "P4",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 16:05:40",
         "iso": "2026-10-10T16:05:40+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员AF",
        "action": "派线路维护部现场抢修。",
        "step_kind": "technical_action"
       },
       {
        "id": "P5",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "field_engineer",
        "time": {
         "raw": "2026-10-10 16:48:22",
         "iso": "2026-10-10T16:48:22+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "线路工程师AG",
        "action": "现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。",
        "step_kind": "technical_action"
       },
       {
        "id": "P6",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 18:57:05",
         "iso": "2026-10-10T18:57:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "线路工程师AG",
        "action": "18:55 熔接完成。",
        "step_kind": "technical_action"
       },
       {
        "id": "P7",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 19:16:31",
         "iso": "2026-10-10T19:16:31+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员AF",
        "action": "19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。",
        "step_kind": "communication"
       },
       {
        "id": "P8",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 19:18:00",
         "iso": "2026-10-10T19:18:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员AF",
        "action": "返单。",
        "step_kind": "workflow"
       },
       {
        "id": "P9",
        "evidence_refs": [
         "M02/log:9"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-10 20:30:12",
         "iso": "2026-10-10T20:30:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "线路工程师AG",
        "action": "上传现场抢修报告（PDF）。",
        "step_kind": "technical_action"
       },
       {
        "id": "P10",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-11 10:20:45",
         "iso": "2026-10-11T10:20:45+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "线路维护部主管AH",
        "action": "责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。",
        "step_kind": "communication"
       },
       {
        "id": "P11",
        "evidence_refs": [
         "M02/log:11"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-11 11:00:00",
         "iso": "2026-10-11T11:00:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员AI",
        "action": "结单。",
        "step_kind": "workflow"
       }
      ]
     },
     "location": {
      "status": "conflicted",
      "evidence_refs": [],
      "issues": [
       "LOCATION_NOT_LOCATED"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "field_engineer",
        "description": "现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。",
        "role": "located_fault_point"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M03/p1:b5"
        ],
        "attribution": "field_engineer",
        "description": "故障点：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m",
        "role": "located_fault_point"
       }
      ]
     }
    },
    "issues": [
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "start_time",
      "evidence_refs": [
       "M01/f:created_at",
       "M01/f:occurred_at",
       "M02/log:1",
       "M02/log:3",
       "M03/p1:b4"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:6",
       "M02/log:7",
       "M02/log:8",
       "M02/log:11"
      ]
     },
     {
      "code": "LOCATION_NOT_LOCATED",
      "severity": "info",
      "message": "未定位实际故障点，业务端点、告警位置和测试节点只作候选。",
      "element": "location",
      "evidence_refs": [
       "M02/log:5",
       "M03/p1:b5"
      ]
     }
    ],
    "suggestions": []
   },
   "company_report": {
    "ticket_ref": "SYN-P04",
    "report_date": "2026年 10 月 29 日",
    "synthetic": true,
    "cells": [
     {
      "row": 0,
      "col": 0,
      "rowspan": 7,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障基本情况",
         "pending": false
        }
       ],
       [
        {
         "text": "The basic situation of failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "客户名称Customer",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "示例客户壬（合成）",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "电路编号",
         "pending": false
        }
       ],
       [
        {
         "text": "Circuit ID.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-CKT-1024",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障号: ",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault Ticket no.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-P04",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "业务类型 Service",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "业务中断",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 1,
      "rowspan": 3,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障时间 Downtime",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "申报时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Time to declare",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-10-10 15:42:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "恢复时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Resumed time",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-10-10 19:08:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障历时",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault duration",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "206分钟",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障现象",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "客户反馈：客户报专线 SYN-CKT-1024 业务中断。；检查显示：查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。；检查显示：19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。；现场工程师称：告警时间：2026-10-10 15:42（R_LOS）；现场工程师称：19:08 网管确认告警清除，业务恢复。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "处理过程",
         "pending": false
        }
       ],
       [
        {
         "text": "Process",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-10-10 15:50:08 GMT+8",
         "pending": false
        },
        {
         "text": " 系统 客户来电报障建单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 15:52:30 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员AF 已受理。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 15:58:14 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员AF 查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS；OTDR 测试显示断点距 A 端局站约 3.2 km。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 16:05:40 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员AF 派线路维护部现场抢修。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 16:48:22 GMT+8",
         "pending": false
        },
        {
         "text": " 线路工程师AG 现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 18:57:05 GMT+8",
         "pending": false
        },
        {
         "text": " 线路工程师AG 18:55 熔接完成。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 19:16:31 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员AF 19:08 告警清除，业务恢复；19:15 客户电话确认业务正常。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 19:18:00 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员AF 返单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-10 20:30:12 GMT+8",
         "pending": false
        },
        {
         "text": " 线路工程师AG 上传现场抢修报告（PDF）。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-11 10:20:45 GMT+8",
         "pending": false
        },
        {
         "text": " 线路维护部主管AH 责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-11 11:00:00 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员AI 结单。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障原因",
         "pending": false
        }
       ],
       [
        {
         "text": "分析",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure Analysis",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "现场确认：示例路与示例大道交叉口人井 SYN-MH-0102 东侧约 15 m 处，市政道路施工挖断 24 芯光缆，施工时间约 15:40。开始抢修。",
         "pending": false
        }
       ],
       [
        {
         "text": "责任方：",
         "pending": false
        },
        {
         "text": "责任认定：本次中断由第三方施工单位示例建设公司（合成）未按管线交底施工造成，责任方为该施工单位，已启动索赔。",
         "pending": false
        },
        {
         "text": "；故障位置：",
         "pending": false
        },
        {
         "text": "【待核实：有冲突】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "改进及预防措施",
         "pending": false
        }
       ],
       [
        {
         "text": "Improvement and preventive measures",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "国际公司将持续关注线路运行情况，监控线路运行情况，发现隐患尽早处理，快速响应处置故障。",
         "pending": false
        },
        {
         "text": "【系统默认表述，待审核】",
         "pending": true
        }
       ]
      ]
     }
    ]
   }
  },
  {
   "ticket": {
    "ticket_ref": "SYN-S09",
    "title": "【合成】跨境专线远端丢包",
    "category": "业务性能-丢包",
    "list_status": "索要报告/结单签收",
    "data_class": "synthetic",
    "captured": "2026-09-29T10:30:00+08:00"
   },
   "downloads": {
    "docx": "samples/SYN-S09-company-report.docx",
    "html": "samples/SYN-S09-company-report.html"
   },
   "analysis": {
    "schema_version": "1.0",
    "ticket_ref": "SYN-S09",
    "data_class": "synthetic",
    "data_cutoff": "2026-09-29T10:30:00+08:00",
    "run": {
     "provider": "rules",
     "rules_version": "1.2",
     "prompt_version": null,
     "finished_at": "2026-10-29T04:53:45.958449+00:00"
    },
    "materials": [
     {
      "id": "M01",
      "kind": "ticket_fields",
      "path": "ticket.json",
      "parse_status": "parsed"
     },
     {
      "id": "M02",
      "kind": "process_log",
      "path": "process_log.json",
      "parse_status": "parsed"
     }
    ],
    "evidence": [
     {
      "id": "M01/f:ticket_no",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "ticket_no"
      },
      "text": "SYN-S09"
     },
     {
      "id": "M01/f:customer",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "customer"
      },
      "text": "Example Corp B（合成）"
     },
     {
      "id": "M01/f:circuit_id",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "circuit_id"
      },
      "text": "SYN-CKT-1009"
     },
     {
      "id": "M01/f:created_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "created_at"
      },
      "text": "2026-09-28 13:02:41"
     },
     {
      "id": "M01/f:fault_type",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "fault_type"
      },
      "text": "业务性能-丢包"
     },
     {
      "id": "M01/f:occurred_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "occurred_at"
      },
      "text": "2026-09-28 13:00:00"
     },
     {
      "id": "M01/f:recovered_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "recovered_at"
      },
      "text": "2026-09-28 13:36:00"
     },
     {
      "id": "M01/f:duration_returned",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "duration_returned"
      },
      "text": "18分钟"
     },
     {
      "id": "M01/f:description",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "description"
      },
      "text": "Circuit ID: SYN-CKT-1009\nTime Circuit Failed: NA\nIssue: We see about 25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong).\nNote: Intrusive testing is NOT approved. Please schedule a test window with us in advance.\n\nBest regards,\nJohn Doe | Network Operations | Example Corp B\nTel: +1-555-0100\nThis email and any attachments are confidential and intended solely for the addressee."
     },
     {
      "id": "M01/f:cause",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "cause"
      },
      "text": "本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。"
     },
     {
      "id": "M02/log:1",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 1
      },
      "text": "根据客户邮件建单。"
     },
     {
      "id": "M02/log:2",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 2
      },
      "text": "已受理。"
     },
     {
      "id": "M02/log:3",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 3
      },
      "text": "本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。"
     },
     {
      "id": "M02/log:4",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 4
      },
      "text": "本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。"
     },
     {
      "id": "M02/log:5",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 5
      },
      "text": "检查 PE 端口流量与错包计数：流量正常，无 CRC 错包。"
     },
     {
      "id": "M02/log:6",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 6
      },
      "text": "返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。"
     },
     {
      "id": "M02/log:7",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 7
      },
      "text": "已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。"
     },
     {
      "id": "M02/log:8",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 8
      },
      "text": "客户暂未提供测试资料。"
     },
     {
      "id": "M02/log:9",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 9
      },
      "text": "工单进入索要报告/结单签收环节。"
     }
    ],
    "elements": {
     "start_time": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:occurred_at"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-09-28 13:00:00",
       "iso": "2026-09-28T13:00:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C2",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:created_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-28 13:02:41",
         "iso": "2026-09-28T13:02:41+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:occurred_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-28 13:00:00",
         "iso": "2026-09-28T13:00:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "fault_start_field"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-28 13:02:41",
         "iso": "2026-09-28T13:02:41+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       }
      ]
     },
     "end_time": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:recovered_at"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER",
       "RECOVERY_UNVERIFIED",
       "RECOVERY_SCOPE_LIMITED"
      ],
      "value": {
       "raw": "2026-09-28 13:36:00",
       "iso": "2026-09-28T13:36:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C1",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:recovered_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-28 13:36:00",
         "iso": "2026-09-28T13:36:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "recovery_field"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-28 13:20:47",
         "iso": "2026-09-28T13:20:47+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_returned"
       }
      ]
     },
     "phenomenon": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:description",
       "M02/log:3",
       "M02/log:4",
       "M02/log:6"
      ],
      "issues": [
       "OBSERVATION_SCOPE_DIFFERS"
      ],
      "value": "客户反馈：Circuit ID: SYN-CKT-1009\nTime Circuit Failed: NA\nIssue: We see about 25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong).\nNote: Intrusive testing is NOT approved. Please schedule a test window with us in advance.；检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。；检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。；检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "description": "Circuit ID: SYN-CKT-1009\nTime Circuit Failed: NA\nIssue: We see about 25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong).\nNote: Intrusive testing is NOT approved. Please schedule a test window with us in advance.",
        "metric": "丢包率",
        "value": 25.0,
        "unit": "%",
        "scope": "Circuit ID: SYN-CKT-1009\nTime Circuit Failed: NA\nIssue: We see about 25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong).\nNote: Intrusive testing is NOT approved. Please schedule a test window with us in advance."
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。",
        "metric": "丢包率",
        "value": 2.0,
        "unit": "ms",
        "scope": "本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "description": "本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。",
        "metric": "丢包率",
        "value": 3.0,
        "unit": "ms",
        "scope": "本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "description": "返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
        "metric": "丢包率",
        "scope": "返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。"
       }
      ]
     },
     "responsible_party": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "RESPONSIBILITY_NO_BASIS"
      ],
      "candidates": []
     },
     "cause": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "CAUSE_NOT_DIAGNOSIS"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "statement": "本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
        "cause_kind": "investigation_finding"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "statement": "本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。",
        "cause_kind": "investigation_finding"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "statement": "本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。",
        "cause_kind": "investigation_finding"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "statement": "返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
        "cause_kind": "investigation_finding"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "noc_check",
        "statement": "客户暂未提供测试资料。",
        "cause_kind": "process_blocker"
       }
      ]
     },
     "handling_process": {
      "status": "documented",
      "evidence_refs": [
       "M02/log:1",
       "M02/log:2",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5",
       "M02/log:6",
       "M02/log:7",
       "M02/log:8",
       "M02/log:9"
      ],
      "issues": [],
      "value": [
       {
        "id": "P1",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:02:41",
         "iso": "2026-09-28T13:02:41+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "系统",
        "action": "根据客户邮件建单。",
        "step_kind": "workflow"
       },
       {
        "id": "P2",
        "evidence_refs": [
         "M02/log:2"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:05:10",
         "iso": "2026-09-28T13:05:10+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员N",
        "action": "已受理。",
        "step_kind": "workflow"
       },
       {
        "id": "P3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:09:55",
         "iso": "2026-09-28T13:09:55+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员N",
        "action": "本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。",
        "step_kind": "check_result"
       },
       {
        "id": "P4",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:14:20",
         "iso": "2026-09-28T13:14:20+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员N",
        "action": "本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。",
        "step_kind": "check_result"
       },
       {
        "id": "P5",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:18:02",
         "iso": "2026-09-28T13:18:02+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员N",
        "action": "检查 PE 端口流量与错包计数：流量正常，无 CRC 错包。",
        "step_kind": "check_result"
       },
       {
        "id": "P6",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:20:47",
         "iso": "2026-09-28T13:20:47+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员N",
        "action": "返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
        "step_kind": "workflow"
       },
       {
        "id": "P7",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-28 13:40:30",
         "iso": "2026-09-28T13:40:30+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "客户经理P",
        "action": "已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。",
        "step_kind": "check_result"
       },
       {
        "id": "P8",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-29 10:00:12",
         "iso": "2026-09-29T10:00:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "客户经理P",
        "action": "客户暂未提供测试资料。",
        "step_kind": "check_result"
       },
       {
        "id": "P9",
        "evidence_refs": [
         "M02/log:9"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-29 10:02:00",
         "iso": "2026-09-29T10:02:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "系统",
        "action": "工单进入索要报告/结单签收环节。",
        "step_kind": "workflow"
       }
      ]
     },
     "location": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "LOCATION_NOT_LOCATED"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "description": "Circuit ID: SYN-CKT-1009\nTime Circuit Failed: NA\nIssue: We see about 25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong).\nNote: Intrusive testing is NOT approved. Please schedule a test window with us in advance.",
        "role": "test_node"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "description": "本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
        "role": "test_node"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。",
        "role": "test_node"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "description": "本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。",
        "role": "test_node"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "description": "返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
        "role": "test_node"
       },
       {
        "id": "C6",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "description": "已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。",
        "role": "test_node"
       }
      ]
     }
    },
    "issues": [
     {
      "code": "DURATION_BASIS_MISMATCH",
      "severity": "info",
      "message": "返单历时 18 分钟与系统字段差 36 分钟不同，不能混用口径。",
      "element": null,
      "evidence_refs": [
       "M01/f:duration_returned"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "start_time",
      "evidence_refs": [
       "M01/f:created_at",
       "M01/f:occurred_at",
       "M02/log:1"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:6"
      ]
     },
     {
      "code": "RECOVERY_UNVERIFIED",
      "severity": "warning",
      "message": "有业务恢复记载，缺少客户恢复确认关系；同意结单不等于确认恢复。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:recovered_at"
      ]
     },
     {
      "code": "CAUSE_NOT_DIAGNOSIS",
      "severity": "warning",
      "message": "推测及其他非正式原因类别保留为候选，不能当作已确认根因。",
      "element": "cause",
      "evidence_refs": [
       "M01/f:cause",
       "M02/log:3",
       "M02/log:4",
       "M02/log:6",
       "M02/log:8"
      ]
     },
     {
      "code": "RESPONSIBILITY_NO_BASIS",
      "severity": "info",
      "message": "未见明确责任认定，不按供应商或处理部门补齐。",
      "element": "responsible_party",
      "evidence_refs": []
     },
     {
      "code": "RECOVERY_SCOPE_LIMITED",
      "severity": "warning",
      "message": "检查范围内正常不能替代业务恢复确认。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:cause",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5",
       "M02/log:6"
      ]
     },
     {
      "code": "OBSERVATION_SCOPE_DIFFERS",
      "severity": "warning",
      "message": "客户感知与网管观测来源、时刻或范围不同，分别保留。",
      "element": "phenomenon",
      "evidence_refs": [
       "M01/f:description",
       "M02/log:3",
       "M02/log:4",
       "M02/log:6"
      ]
     },
     {
      "code": "LOCATION_NOT_LOCATED",
      "severity": "info",
      "message": "未定位实际故障点，业务端点、告警位置和测试节点只作候选。",
      "element": "location",
      "evidence_refs": [
       "M01/f:description",
       "M01/f:cause",
       "M02/log:3",
       "M02/log:4",
       "M02/log:6",
       "M02/log:7"
      ]
     }
    ],
    "suggestions": [
     {
      "element": "location",
      "label": "故障地点",
      "design_sample": true,
      "candidates": [
       {
        "text": "法兰克福代理节点至香港目标网段之间的跨境段（客户感知丢包的路径）",
        "role": "客户感知路径，不是已定位的故障点",
        "evidence_refs": [
         "M01/f:description"
        ],
        "quote": "25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong)",
        "quote_check": "match"
       }
      ]
     },
     {
      "element": "responsible_party",
      "label": "故障责任方",
      "design_sample": true,
      "candidates": [
       {
        "text": "境外对端运营商",
        "role": "模型推测，材料里没有任何一方被认定为责任方",
        "evidence_refs": [
         "M01/f:description"
        ],
        "quote": "the remote carrier is dropping packets",
        "quote_check": "mismatch"
       }
      ]
     }
    ]
   },
   "company_report": {
    "ticket_ref": "SYN-S09",
    "report_date": "2026年 10 月 29 日",
    "synthetic": true,
    "cells": [
     {
      "row": 0,
      "col": 0,
      "rowspan": 7,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障基本情况",
         "pending": false
        }
       ],
       [
        {
         "text": "The basic situation of failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "客户名称Customer",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "Example Corp B（合成）",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "电路编号",
         "pending": false
        }
       ],
       [
        {
         "text": "Circuit ID.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-CKT-1009",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障号: ",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault Ticket no.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-S09",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "业务类型 Service",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "业务性能-丢包",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 1,
      "rowspan": 3,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障时间 Downtime",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "申报时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Time to declare",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-28 13:00:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "恢复时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Resumed time",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-28 13:36:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障历时",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault duration",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "约 36 分钟",
         "pending": false
        },
        {
         "text": "【待核实：恢复未确认】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障现象",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "客户反馈：Circuit ID: SYN-CKT-1009",
         "pending": false
        }
       ],
       [
        {
         "text": "Time Circuit Failed: NA",
         "pending": false
        }
       ],
       [
        {
         "text": "Issue: We see about 25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong).",
         "pending": false
        }
       ],
       [
        {
         "text": "Note: Intrusive testing is NOT approved. Please schedule a test window with us in advance.；检查显示：本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。；检查显示：本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。；检查显示：返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "处理过程",
         "pending": false
        }
       ],
       [
        {
         "text": "Process",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-28 13:02:41 GMT+8",
         "pending": false
        },
        {
         "text": " 系统 根据客户邮件建单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-28 13:05:10 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员N 已受理。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-28 13:09:55 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员N 本端 PE ping 客户 CE 互联地址：100 发 100 收，无丢包，平均 RTT 2 ms。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-28 13:14:20 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员N 本端 PE ping 香港侧目标网段网关：100 发 100 收，无丢包，平均 RTT 3 ms。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-28 13:18:02 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员N 检查 PE 端口流量与错包计数：流量正常，无 CRC 错包。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-28 13:20:47 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员N 返单：本端 ping 测试 100 发 100 收，无丢包，端口流量正常；请客户提供故障时的源/目的地址及 ping/trace 结果。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-28 13:40:30 GMT+8",
         "pending": false
        },
        {
         "text": " 客户经理P 已转告客户，请其提供故障时源/目的地址及 ping/trace 结果。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-29 10:00:12 GMT+8",
         "pending": false
        },
        {
         "text": " 客户经理P 客户暂未提供测试资料。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-29 10:02:00 GMT+8",
         "pending": false
        },
        {
         "text": " 系统 工单进入索要报告/结单签收环节。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障原因",
         "pending": false
        }
       ],
       [
        {
         "text": "分析",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure Analysis",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "【待核实】",
         "pending": true
        }
       ],
       [
        {
         "text": "责任方：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        },
        {
         "text": "；故障位置：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "改进及预防措施",
         "pending": false
        }
       ],
       [
        {
         "text": "Improvement and preventive measures",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "国际公司将持续关注线路运行情况，监控线路运行情况，发现隐患尽早处理，快速响应处置故障。",
         "pending": false
        },
        {
         "text": "【系统默认表述，待审核】",
         "pending": true
        }
       ]
      ]
     }
    ]
   }
  },
  {
   "ticket": {
    "ticket_ref": "SYN-P01",
    "title": "【合成】城域光缆中断（恢复时间早于发生时间）",
    "category": "业务中断",
    "list_status": "已结单",
    "data_class": "synthetic",
    "captured": "2026-10-06T09:30:00+08:00"
   },
   "downloads": {
    "docx": "samples/SYN-P01-company-report.docx",
    "html": "samples/SYN-P01-company-report.html"
   },
   "analysis": {
    "schema_version": "1.0",
    "ticket_ref": "SYN-P01",
    "data_class": "synthetic",
    "data_cutoff": "2026-10-06T09:30:00+08:00",
    "run": {
     "provider": "rules",
     "rules_version": "1.2",
     "prompt_version": null,
     "finished_at": "2026-10-29T04:53:45.995183+00:00"
    },
    "materials": [
     {
      "id": "M01",
      "kind": "ticket_fields",
      "path": "ticket.json",
      "parse_status": "parsed"
     },
     {
      "id": "M02",
      "kind": "process_log",
      "path": "process_log.json",
      "parse_status": "parsed"
     }
    ],
    "evidence": [
     {
      "id": "M01/f:ticket_no",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "ticket_no"
      },
      "text": "SYN-P01"
     },
     {
      "id": "M01/f:customer",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "customer"
      },
      "text": "示例客户己（合成）"
     },
     {
      "id": "M01/f:circuit_id",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "circuit_id"
      },
      "text": "SYN-CKT-1021"
     },
     {
      "id": "M01/f:created_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "created_at"
      },
      "text": "2026-10-05 23:58:12"
     },
     {
      "id": "M01/f:fault_type",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "fault_type"
      },
      "text": "业务中断"
     },
     {
      "id": "M01/f:occurred_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "occurred_at"
      },
      "text": "2026-10-05 23:50:00"
     },
     {
      "id": "M01/f:recovered_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "recovered_at"
      },
      "text": "2026-10-05 00:20:00"
     },
     {
      "id": "M01/f:duration_returned",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "duration_returned"
      },
      "text": "-1410分钟"
     },
     {
      "id": "M01/f:description",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "description"
      },
      "text": "客户报专线 SYN-CKT-1021 业务中断。"
     },
     {
      "id": "M01/f:cause",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "cause"
      },
      "text": "光缆中断，已熔接恢复。"
     },
     {
      "id": "M02/log:1",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 1
      },
      "text": "客户来电报障建单。"
     },
     {
      "id": "M02/log:2",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 2
      },
      "text": "已受理。"
     },
     {
      "id": "M02/log:3",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 3
      },
      "text": "查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。"
     },
     {
      "id": "M02/log:4",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 4
      },
      "text": "光缆中断点已熔接完成。"
     },
     {
      "id": "M02/log:5",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 5
      },
      "text": "2026-10-06 00:20 告警清除，客户确认业务恢复。"
     },
     {
      "id": "M02/log:6",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 6
      },
      "text": "返单。"
     },
     {
      "id": "M02/log:7",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 7
      },
      "text": "结单。"
     }
    ],
    "elements": {
     "start_time": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:occurred_at"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-10-05 23:50:00",
       "iso": "2026-10-05T23:50:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C2",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:created_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-05 23:58:12",
         "iso": "2026-10-05T23:58:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:occurred_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-05 23:50:00",
         "iso": "2026-10-05T23:50:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "fault_start_field"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-05 23:58:12",
         "iso": "2026-10-05T23:58:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:3",
         "M01/f:occurred_at"
        ],
        "attribution": "noc_check",
        "note": "原文只有时刻；日期与同单对应起止字段对齐，保留两处依据。",
        "time": {
         "raw": "23:50",
         "iso": "2026-10-05T23:50:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "alarm_raised"
       }
      ]
     },
     "end_time": {
      "status": "conflicted",
      "evidence_refs": [],
      "issues": [
       "TIME_ORDER_INVERTED",
       "NEGATIVE_DURATION",
       "TIME_CANDIDATES_DIFFER",
       "ONGOING_NO_END"
      ],
      "note": "时间候选不同，保留原值待核实。",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:recovered_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-05 00:20:00",
         "iso": "2026-10-05T00:20:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "recovery_field"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-10-06 00:20",
         "iso": "2026-10-06T00:20:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "customer_confirmed_recovery"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-06 00:30:00",
         "iso": "2026-10-06T00:30:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_returned"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-10-06 09:00:00",
         "iso": "2026-10-06T09:00:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       }
      ]
     },
     "phenomenon": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:description",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5"
      ],
      "issues": [],
      "value": "客户反馈：客户报专线 SYN-CKT-1021 业务中断。；检查显示：查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。；检查显示：光缆中断点已熔接完成。；客户反馈：2026-10-06 00:20 告警清除，客户确认业务恢复。",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "description": "客户报专线 SYN-CKT-1021 业务中断。",
        "metric": "告警/状态",
        "scope": "客户报专线 SYN-CKT-1021 业务中断。"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。",
        "metric": "告警/状态",
        "scope": "查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "description": "光缆中断点已熔接完成。",
        "metric": "告警/状态",
        "scope": "光缆中断点已熔接完成。"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "customer",
        "description": "2026-10-06 00:20 告警清除，客户确认业务恢复。",
        "metric": "告警/状态",
        "scope": "2026-10-06 00:20 告警清除，客户确认业务恢复。"
       }
      ]
     },
     "responsible_party": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "RESPONSIBILITY_NO_BASIS"
      ],
      "candidates": []
     },
     "cause": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:cause"
      ],
      "issues": [],
      "value": "光缆中断，已熔接恢复。",
      "selected": "C1",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "statement": "光缆中断，已熔接恢复。",
        "cause_kind": "root_cause_claimed"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "statement": "光缆中断点已熔接完成。",
        "cause_kind": "root_cause_claimed"
       }
      ]
     },
     "handling_process": {
      "status": "documented",
      "evidence_refs": [
       "M02/log:1",
       "M02/log:2",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5",
       "M02/log:6",
       "M02/log:7"
      ],
      "issues": [],
      "value": [
       {
        "id": "P1",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-10-05 23:58:12",
         "iso": "2026-10-05T23:58:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "系统",
        "action": "客户来电报障建单。",
        "step_kind": "workflow"
       },
       {
        "id": "P2",
        "evidence_refs": [
         "M02/log:2"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-06 00:01:30",
         "iso": "2026-10-06T00:01:30+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员X",
        "action": "已受理。",
        "step_kind": "workflow"
       },
       {
        "id": "P3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-06 00:05:47",
         "iso": "2026-10-06T00:05:47+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员X",
        "action": "查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。",
        "step_kind": "check_result"
       },
       {
        "id": "P4",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-06 00:16:02",
         "iso": "2026-10-06T00:16:02+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "线路工程师Y",
        "action": "光缆中断点已熔接完成。",
        "step_kind": "technical_action"
       },
       {
        "id": "P5",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-10-06 00:24:40",
         "iso": "2026-10-06T00:24:40+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员X",
        "action": "2026-10-06 00:20 告警清除，客户确认业务恢复。",
        "step_kind": "communication"
       },
       {
        "id": "P6",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-06 00:30:00",
         "iso": "2026-10-06T00:30:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员X",
        "action": "返单。",
        "step_kind": "workflow"
       },
       {
        "id": "P7",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-10-06 09:00:00",
         "iso": "2026-10-06T09:00:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员Z",
        "action": "结单。",
        "step_kind": "workflow"
       }
      ]
     },
     "location": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "LOCATION_NOT_LOCATED"
      ],
      "candidates": []
     }
    },
    "issues": [
     {
      "code": "TIME_ORDER_INVERTED",
      "severity": "critical",
      "message": "系统恢复字段早于发生字段，保留原值待核实。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:occurred_at",
       "M01/f:recovered_at"
      ]
     },
     {
      "code": "NEGATIVE_DURATION",
      "severity": "critical",
      "message": "系统起止字段差为负，不能生成有效故障历时。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:occurred_at",
       "M01/f:recovered_at"
      ]
     },
     {
      "code": "NEGATIVE_DURATION",
      "severity": "critical",
      "message": "返单历时为负，需核对原始口径。",
      "element": null,
      "evidence_refs": [
       "M01/f:duration_returned"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "start_time",
      "evidence_refs": [
       "M01/f:created_at",
       "M01/f:occurred_at",
       "M02/log:1",
       "M02/log:3"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:5",
       "M02/log:6",
       "M02/log:7"
      ]
     },
     {
      "code": "ONGOING_NO_END",
      "severity": "info",
      "message": "未获得无冲突的恢复时间，不计算最终历时。",
      "element": "end_time",
      "evidence_refs": []
     },
     {
      "code": "RESPONSIBILITY_NO_BASIS",
      "severity": "info",
      "message": "未见明确责任认定，不按供应商或处理部门补齐。",
      "element": "responsible_party",
      "evidence_refs": []
     },
     {
      "code": "LOCATION_NOT_LOCATED",
      "severity": "info",
      "message": "未定位实际故障点，业务端点、告警位置和测试节点只作候选。",
      "element": "location",
      "evidence_refs": []
     }
    ],
    "suggestions": []
   },
   "company_report": {
    "ticket_ref": "SYN-P01",
    "report_date": "2026年 10 月 29 日",
    "synthetic": true,
    "cells": [
     {
      "row": 0,
      "col": 0,
      "rowspan": 7,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障基本情况",
         "pending": false
        }
       ],
       [
        {
         "text": "The basic situation of failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "客户名称Customer",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "示例客户己（合成）",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "电路编号",
         "pending": false
        }
       ],
       [
        {
         "text": "Circuit ID.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-CKT-1021",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障号: ",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault Ticket no.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-P01",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "业务类型 Service",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "业务中断",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 1,
      "rowspan": 3,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障时间 Downtime",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "申报时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Time to declare",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-10-05 23:50:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "恢复时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Resumed time",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "【待核实：时间有冲突】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障历时",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault duration",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "【待核实】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障现象",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "客户反馈：客户报专线 SYN-CKT-1021 业务中断。；检查显示：查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。；检查显示：光缆中断点已熔接完成。；客户反馈：2026-10-06 00:20 告警清除，客户确认业务恢复。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "处理过程",
         "pending": false
        }
       ],
       [
        {
         "text": "Process",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-10-05 23:58:12 GMT+8",
         "pending": false
        },
        {
         "text": " 系统 客户来电报障建单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-06 00:01:30 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员X 已受理。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-06 00:05:47 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员X 查告警：23:50 起 SYN-CKT-1021 所在光缆段 R_LOS，派线路维护处理。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-06 00:16:02 GMT+8",
         "pending": false
        },
        {
         "text": " 线路工程师Y 光缆中断点已熔接完成。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-06 00:24:40 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员X 2026-10-06 00:20 告警清除，客户确认业务恢复。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-06 00:30:00 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员X 返单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-10-06 09:00:00 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员Z 结单。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障原因",
         "pending": false
        }
       ],
       [
        {
         "text": "分析",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure Analysis",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "光缆中断，已熔接恢复。",
         "pending": false
        }
       ],
       [
        {
         "text": "责任方：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        },
        {
         "text": "；故障位置：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "改进及预防措施",
         "pending": false
        }
       ],
       [
        {
         "text": "Improvement and preventive measures",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "国际公司将持续关注线路运行情况，监控线路运行情况，发现隐患尽早处理，快速响应处置故障。",
         "pending": false
        },
        {
         "text": "【系统默认表述，待审核】",
         "pending": true
        }
       ]
      ]
     }
    ]
   }
  },
  {
   "ticket": {
    "ticket_ref": "SYN-S06",
    "title": "【合成】东京—香港大客户电路丢包",
    "category": "业务性能-丢包",
    "list_status": "已结单",
    "data_class": "synthetic",
    "captured": "2026-09-25T12:00:00+08:00"
   },
   "downloads": {
    "docx": "samples/SYN-S06-company-report.docx",
    "html": "samples/SYN-S06-company-report.html"
   },
   "analysis": {
    "schema_version": "1.0",
    "ticket_ref": "SYN-S06",
    "data_class": "synthetic",
    "data_cutoff": "2026-09-25T12:00:00+08:00",
    "run": {
     "provider": "rules",
     "rules_version": "1.2",
     "prompt_version": null,
     "finished_at": "2026-10-29T04:53:46.032895+00:00"
    },
    "materials": [
     {
      "id": "M01",
      "kind": "ticket_fields",
      "path": "ticket.json",
      "parse_status": "parsed"
     },
     {
      "id": "M02",
      "kind": "process_log",
      "path": "process_log.json",
      "parse_status": "parsed"
     },
     {
      "id": "M03",
      "kind": "email_html",
      "path": "emails/M03-vendor-reply.html",
      "parse_status": "parsed"
     }
    ],
    "evidence": [
     {
      "id": "M01/f:ticket_no",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "ticket_no"
      },
      "text": "SYN-S06"
     },
     {
      "id": "M01/f:customer",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "customer"
      },
      "text": "示例客户丁（合成）"
     },
     {
      "id": "M01/f:circuit_id",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "circuit_id"
      },
      "text": "SYN-CKT-1006"
     },
     {
      "id": "M01/f:a_end",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "a_end"
      },
      "text": "东京 示例 PoP（合成）"
     },
     {
      "id": "M01/f:z_end",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "z_end"
      },
      "text": "香港 示例 PoP（合成）"
     },
     {
      "id": "M01/f:vendor",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "vendor"
      },
      "text": "上游运营商 JP-Carrier（合成）"
     },
     {
      "id": "M01/f:created_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "created_at"
      },
      "text": "2026-09-25 09:20:05"
     },
     {
      "id": "M01/f:fault_type",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "fault_type"
      },
      "text": "业务性能-丢包"
     },
     {
      "id": "M01/f:occurred_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "occurred_at"
      },
      "text": "2026-09-25 09:40:00"
     },
     {
      "id": "M01/f:recovered_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "recovered_at"
      },
      "text": "2026-09-25 10:01:00"
     },
     {
      "id": "M01/f:duration_returned",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "duration_returned"
      },
      "text": "63分钟"
     },
     {
      "id": "M01/f:description",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "description"
      },
      "text": "客户报东京—香港电路 SYN-CKT-1006 丢包约 86%，视频会议无法使用。"
     },
     {
      "id": "M01/f:cause",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "cause"
      },
      "text": "自恢"
     },
     {
      "id": "M02/log:1",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 1
      },
      "text": "根据客户邮件建单。"
     },
     {
      "id": "M02/log:2",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 2
      },
      "text": "已受理。"
     },
     {
      "id": "M02/log:3",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 3
      },
      "text": "本端 ping 对端 PE（东京侧）中断，100 发 0 收。"
     },
     {
      "id": "M02/log:4",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 4
      },
      "text": "已邮件报障至上游运营商 JP-Carrier。"
     },
     {
      "id": "M02/log:5",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 5
      },
      "text": "【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。"
     },
     {
      "id": "M02/log:6",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 6
      },
      "text": "客户来电确认：10:01 起业务恢复正常，丢包消失。"
     },
     {
      "id": "M02/log:7",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 7
      },
      "text": "返单。原因：自恢。"
     },
     {
      "id": "M02/log:8",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 8
      },
      "text": "收到上游运营商 JP-Carrier 回复邮件，详见邮件详情。"
     },
     {
      "id": "M02/log:9",
      "material_id": "M02",
      "role": "derived_summary",
      "locator": {
       "type": "log_entry",
       "seq": 9
      },
      "text": "【AI 追单总结】上游运营商回复：其东京侧设备 TYO-PE-02 宕机，登录时连接超时，仍在排查。客户已确认 10:01 恢复。建议继续跟进上游根因。"
     },
     {
      "id": "M02/log:10",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 10
      },
      "text": "结单。"
     },
     {
      "id": "M03/msg:0:header",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "email_message",
       "message_index": 0,
       "part": "header"
      },
      "text": "From: noc@jp-carrier.example.net\nTo: noc@example.com\nDate: Fri, 25 Sep 2026 02:48:10 +0000\nSubject: RE: [SYN-S06] Packet loss on SYN-CKT-1006"
     },
     {
      "id": "M03/msg:0:body",
      "material_id": "M03",
      "role": "original",
      "locator": {
       "type": "email_message",
       "message_index": 0,
       "part": "body"
      },
      "text": "Dear NOC,\nWe found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.\n$ ssh admin@198.51.100.7\nssh: connect to host 198.51.100.7 port 22: Connection timed out\nWe will update you once the root cause is identified."
     },
     {
      "id": "M03/msg:0:signature",
      "material_id": "M03",
      "role": "signature",
      "locator": {
       "type": "email_message",
       "message_index": 0,
       "part": "signature"
      },
      "text": "Best regards,\nJP-Carrier NOC (synthetic)\nTel: +81-3-0000-0000\nCONFIDENTIALITY NOTICE: This e-mail and any attachments are confidential. 本邮件及其附件含保密信息。"
     },
     {
      "id": "M03/msg:1:header",
      "material_id": "M03",
      "role": "quoted",
      "locator": {
       "type": "email_message",
       "message_index": 1,
       "part": "header"
      },
      "text": "From: noc@example.com\nTo: noc@jp-carrier.example.net\nDate: Fri, 25 Sep 2026 01:35:20 +0000\nSubject: [SYN-S06] Packet loss on SYN-CKT-1006"
     },
     {
      "id": "M03/msg:1:body",
      "material_id": "M03",
      "role": "quoted",
      "locator": {
       "type": "email_message",
       "message_index": 1,
       "part": "body"
      },
      "text": "Dear JP-Carrier NOC,\nOur customer reports about 86% packet loss on circuit SYN-CKT-1006 (Tokyo - Hong Kong) since 09:15 GMT+8. Ping from our side to TYO PE fails. Please check your segment."
     },
     {
      "id": "M03/msg:1:signature",
      "material_id": "M03",
      "role": "signature",
      "locator": {
       "type": "email_message",
       "message_index": 1,
       "part": "signature"
      },
      "text": "Regards,\nNOC (synthetic)"
     },
     {
      "id": "M03/msg:2:header",
      "material_id": "M03",
      "role": "quoted",
      "locator": {
       "type": "email_message",
       "message_index": 2,
       "part": "header"
      },
      "text": "From: it@customer-d.example.org\nTo: noc@example.com\nDate: Fri, 25 Sep 2026 09:16:42 +0800\nSubject: Heavy packet loss Tokyo - HK"
     },
     {
      "id": "M03/msg:2:body",
      "material_id": "M03",
      "role": "quoted",
      "locator": {
       "type": "email_message",
       "message_index": 2,
       "part": "body"
      },
      "text": "Hi,\nSince around 09:15 this morning (GMT+8) we see heavy packet loss (about 86%) on the Tokyo - Hong Kong link SYN-CKT-1006. Video conferencing is unusable."
     },
     {
      "id": "M03/msg:2:signature",
      "material_id": "M03",
      "role": "signature",
      "locator": {
       "type": "email_message",
       "message_index": 2,
       "part": "signature"
      },
      "text": "Thanks,\nIT team, Customer D (synthetic)"
     }
    ],
    "elements": {
     "start_time": {
      "status": "conflicted",
      "evidence_refs": [],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "note": "时间候选不同，保留原值待核实。",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:created_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-25 09:20:05",
         "iso": "2026-09-25T09:20:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:occurred_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-25 09:40:00",
         "iso": "2026-09-25T09:40:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "fault_start_field"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-25 09:20:05",
         "iso": "2026-09-25T09:20:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M03/msg:1:body"
        ],
        "attribution": "customer",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "09:15 GMT+8",
         "iso": "2026-09-25T09:15:00+08:00",
         "tz_source": "explicit",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "customer_reported_start"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M03/msg:2:body"
        ],
        "attribution": "customer",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "09:15 this morning (GMT+8)",
         "iso": "2026-09-25T09:15:00+08:00",
         "tz_source": "explicit",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "customer_reported_start"
       }
      ]
     },
     "end_time": {
      "status": "confirmed",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:6"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-09-25 10:01:00",
       "iso": "2026-09-25T10:01:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C1",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:recovered_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-25 10:01:00",
         "iso": "2026-09-25T10:01:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "recovery_field"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "customer",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "10:01",
         "iso": "2026-09-25T10:01:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "customer_confirmed_recovery"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-25 10:23:10",
         "iso": "2026-09-25T10:23:10+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_returned"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-25 11:30:00",
         "iso": "2026-09-25T11:30:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       }
      ]
     },
     "phenomenon": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:description",
       "M02/log:3",
       "M02/log:5",
       "M02/log:6",
       "M03/msg:0:body"
      ],
      "issues": [],
      "value": "客户反馈：客户报东京—香港电路 SYN-CKT-1006 丢包约 86%，视频会议无法使用。；检查显示：本端 ping 对端 PE（东京侧）中断，100 发 0 收。；检查显示：【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。；客户反馈：客户来电确认：10:01 起业务恢复正常，丢包消失。；供应商称：Dear NOC,\nWe found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.\n$ ssh admin@198.51.100.7\nssh: connect to host 198.51.100.7 port 22: Connection timed out\nWe will update you once the root cause is identified.",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "description": "客户报东京—香港电路 SYN-CKT-1006 丢包约 86%，视频会议无法使用。",
        "metric": "丢包率",
        "value": 86.0,
        "unit": "%",
        "scope": "客户报东京—香港电路 SYN-CKT-1006 丢包约 86%，视频会议无法使用。"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "本端 ping 对端 PE（东京侧）中断，100 发 0 收。",
        "metric": "告警/状态",
        "scope": "本端 ping 对端 PE（东京侧）中断，100 发 0 收。"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "noc_check",
        "description": "【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。",
        "metric": "丢包率",
        "value": 10.0,
        "unit": "%",
        "scope": "【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "customer",
        "description": "客户来电确认：10:01 起业务恢复正常，丢包消失。",
        "metric": "丢包率",
        "scope": "客户来电确认：10:01 起业务恢复正常，丢包消失。"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M03/msg:0:body"
        ],
        "attribution": "vendor",
        "description": "Dear NOC,\nWe found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.\n$ ssh admin@198.51.100.7\nssh: connect to host 198.51.100.7 port 22: Connection timed out\nWe will update you once the root cause is identified.",
        "metric": "告警/状态",
        "scope": "Dear NOC,\nWe found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.\n$ ssh admin@198.51.100.7\nssh: connect to host 198.51.100.7 port 22: Connection timed out\nWe will update you once the root cause is identified."
       },
       {
        "id": "C6",
        "evidence_refs": [
         "M03/msg:1:body"
        ],
        "attribution": "customer",
        "description": "Dear JP-Carrier NOC,\nOur customer reports about 86% packet loss on circuit SYN-CKT-1006 (Tokyo - Hong Kong) since 09:15 GMT+8. Ping from our side to TYO PE fails. Please check your segment.",
        "metric": "丢包率",
        "value": 86.0,
        "unit": "%",
        "scope": "Dear JP-Carrier NOC,\nOur customer reports about 86% packet loss on circuit SYN-CKT-1006 (Tokyo - Hong Kong) since 09:15 GMT+8. Ping from our side to TYO PE fails. Please check your segment."
       },
       {
        "id": "C7",
        "evidence_refs": [
         "M03/msg:2:body"
        ],
        "attribution": "customer",
        "description": "Hi,\nSince around 09:15 this morning (GMT+8) we see heavy packet loss (about 86%) on the Tokyo - Hong Kong link SYN-CKT-1006. Video conferencing is unusable.",
        "metric": "丢包率",
        "value": 86.0,
        "unit": "%",
        "scope": "Hi,\nSince around 09:15 this morning (GMT+8) we see heavy packet loss (about 86%) on the Tokyo - Hong Kong link SYN-CKT-1006. Video conferencing is unusable."
       }
      ]
     },
     "responsible_party": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "RESPONSIBILITY_NO_BASIS"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:vendor"
        ],
        "attribution": "system_field",
        "party": "上游运营商 JP-Carrier（合成）",
        "basis": "inferred_from_role"
       }
      ]
     },
     "cause": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "CAUSE_NOT_DIAGNOSIS"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "statement": "自恢",
        "cause_kind": "recovery_mode"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "statement": "返单。原因：自恢。",
        "cause_kind": "recovery_mode"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M03/msg:0:body"
        ],
        "attribution": "vendor",
        "statement": "Dear NOC,\nWe found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.\n$ ssh admin@198.51.100.7\nssh: connect to host 198.51.100.7 port 22: Connection timed out\nWe will update you once the root cause is identified.",
        "cause_kind": "investigation_finding"
       }
      ]
     },
     "handling_process": {
      "status": "documented",
      "evidence_refs": [
       "M02/log:1",
       "M02/log:2",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5",
       "M02/log:6",
       "M02/log:7",
       "M02/log:8",
       "M02/log:10"
      ],
      "issues": [],
      "value": [
       {
        "id": "P1",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 09:20:05",
         "iso": "2026-09-25T09:20:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "系统",
        "action": "根据客户邮件建单。",
        "step_kind": "workflow"
       },
       {
        "id": "P2",
        "evidence_refs": [
         "M02/log:2"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 09:22:40",
         "iso": "2026-09-25T09:22:40+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员L",
        "action": "已受理。",
        "step_kind": "workflow"
       },
       {
        "id": "P3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 09:26:12",
         "iso": "2026-09-25T09:26:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员L",
        "action": "本端 ping 对端 PE（东京侧）中断，100 发 0 收。",
        "step_kind": "check_result"
       },
       {
        "id": "P4",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 09:35:30",
         "iso": "2026-09-25T09:35:30+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员L",
        "action": "已邮件报障至上游运营商 JP-Carrier。",
        "step_kind": "communication"
       },
       {
        "id": "P5",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 09:52:08",
         "iso": "2026-09-25T09:52:08+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "数字员工",
        "action": "【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。",
        "step_kind": "communication"
       },
       {
        "id": "P6",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-09-25 10:05:44",
         "iso": "2026-09-25T10:05:44+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员L",
        "action": "客户来电确认：10:01 起业务恢复正常，丢包消失。",
        "step_kind": "communication"
       },
       {
        "id": "P7",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 10:23:10",
         "iso": "2026-09-25T10:23:10+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员L",
        "action": "返单。原因：自恢。",
        "step_kind": "workflow"
       },
       {
        "id": "P8",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 10:49:31",
         "iso": "2026-09-25T10:49:31+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "邮件系统",
        "action": "收到上游运营商 JP-Carrier 回复邮件，详见邮件详情。",
        "step_kind": "communication"
       },
       {
        "id": "P9",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-25 11:30:00",
         "iso": "2026-09-25T11:30:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员M",
        "action": "结单。",
        "step_kind": "workflow"
       }
      ]
     },
     "location": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "LOCATION_NOT_LOCATED"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:a_end"
        ],
        "attribution": "system_field",
        "description": "东京 示例 PoP（合成）",
        "role": "service_endpoint"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:z_end"
        ],
        "attribution": "system_field",
        "description": "香港 示例 PoP（合成）",
        "role": "service_endpoint"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "本端 ping 对端 PE（东京侧）中断，100 发 0 收。",
        "role": "test_node"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M03/msg:0:body"
        ],
        "attribution": "vendor",
        "description": "Dear NOC,\nWe found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.\n$ ssh admin@198.51.100.7\nssh: connect to host 198.51.100.7 port 22: Connection timed out\nWe will update you once the root cause is identified.",
        "role": "test_node"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M03/msg:1:body"
        ],
        "attribution": "customer",
        "description": "Dear JP-Carrier NOC,\nOur customer reports about 86% packet loss on circuit SYN-CKT-1006 (Tokyo - Hong Kong) since 09:15 GMT+8. Ping from our side to TYO PE fails. Please check your segment.",
        "role": "test_node"
       }
      ]
     }
    },
    "issues": [
     {
      "code": "DURATION_BASIS_MISMATCH",
      "severity": "info",
      "message": "返单历时 63 分钟与系统字段差 21 分钟不同，不能混用口径。",
      "element": null,
      "evidence_refs": [
       "M01/f:duration_returned"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "start_time",
      "evidence_refs": [
       "M01/f:created_at",
       "M01/f:occurred_at",
       "M02/log:1",
       "M03/msg:1:body",
       "M03/msg:2:body"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:6",
       "M02/log:7",
       "M02/log:10"
      ]
     },
     {
      "code": "CAUSE_NOT_DIAGNOSIS",
      "severity": "warning",
      "message": "推测及其他非正式原因类别保留为候选，不能当作已确认根因。",
      "element": "cause",
      "evidence_refs": [
       "M01/f:cause",
       "M02/log:7",
       "M03/msg:0:body"
      ]
     },
     {
      "code": "RESPONSIBILITY_NO_BASIS",
      "severity": "info",
      "message": "未见明确责任认定，不按供应商或处理部门补齐。",
      "element": "responsible_party",
      "evidence_refs": [
       "M01/f:vendor"
      ]
     },
     {
      "code": "LOCATION_NOT_LOCATED",
      "severity": "info",
      "message": "未定位实际故障点，业务端点、告警位置和测试节点只作候选。",
      "element": "location",
      "evidence_refs": [
       "M01/f:a_end",
       "M01/f:z_end",
       "M02/log:3",
       "M03/msg:0:body",
       "M03/msg:1:body"
      ]
     },
     {
      "code": "DERIVED_SOURCE_DUPLICATE",
      "severity": "info",
      "message": "摘要/邮件引用为衍生来源，不作为新增独立佐证。",
      "element": null,
      "evidence_refs": [
       "M02/log:9"
      ]
     },
     {
      "code": "DERIVED_SOURCE_DUPLICATE",
      "severity": "info",
      "message": "摘要/邮件引用为衍生来源，不作为新增独立佐证。",
      "element": null,
      "evidence_refs": [
       "M03/msg:1:header"
      ]
     },
     {
      "code": "DERIVED_SOURCE_DUPLICATE",
      "severity": "info",
      "message": "摘要/邮件引用为衍生来源，不作为新增独立佐证。",
      "element": null,
      "evidence_refs": [
       "M03/msg:1:body"
      ]
     },
     {
      "code": "DERIVED_SOURCE_DUPLICATE",
      "severity": "info",
      "message": "摘要/邮件引用为衍生来源，不作为新增独立佐证。",
      "element": null,
      "evidence_refs": [
       "M03/msg:2:header"
      ]
     },
     {
      "code": "DERIVED_SOURCE_DUPLICATE",
      "severity": "info",
      "message": "摘要/邮件引用为衍生来源，不作为新增独立佐证。",
      "element": null,
      "evidence_refs": [
       "M03/msg:2:body"
      ]
     }
    ],
    "suggestions": []
   },
   "company_report": {
    "ticket_ref": "SYN-S06",
    "report_date": "2026年 10 月 29 日",
    "synthetic": true,
    "cells": [
     {
      "row": 0,
      "col": 0,
      "rowspan": 7,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障基本情况",
         "pending": false
        }
       ],
       [
        {
         "text": "The basic situation of failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "客户名称Customer",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "示例客户丁（合成）",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "电路编号",
         "pending": false
        }
       ],
       [
        {
         "text": "Circuit ID.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-CKT-1006",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障号: ",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault Ticket no.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-S06",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "业务类型 Service",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "业务性能-丢包",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 1,
      "rowspan": 3,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障时间 Downtime",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "申报时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Time to declare",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "【待核实：时间有冲突】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "恢复时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Resumed time",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-25 10:01:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障历时",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault duration",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "【待核实】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障现象",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "客户反馈：客户报东京—香港电路 SYN-CKT-1006 丢包约 86%，视频会议无法使用。；检查显示：本端 ping 对端 PE（东京侧）中断，100 发 0 收。；检查显示：【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。；客户反馈：客户来电确认：10:01 起业务恢复正常，丢包消失。；供应商称：Dear NOC,",
         "pending": false
        }
       ],
       [
        {
         "text": "We found that our device TYO-PE-02 is down. Login attempts time out; our field team is investigating.",
         "pending": false
        }
       ],
       [
        {
         "text": "$ ssh admin@198.51.100.7",
         "pending": false
        }
       ],
       [
        {
         "text": "ssh: connect to host 198.51.100.7 port 22: Connection timed out",
         "pending": false
        }
       ],
       [
        {
         "text": "We will update you once the root cause is identified.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "处理过程",
         "pending": false
        }
       ],
       [
        {
         "text": "Process",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-25 09:20:05 GMT+8",
         "pending": false
        },
        {
         "text": " 系统 根据客户邮件建单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 09:22:40 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员L 已受理。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 09:26:12 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员L 本端 ping 对端 PE（东京侧）中断，100 发 0 收。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 09:35:30 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员L 已邮件报障至上游运营商 JP-Carrier。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 09:52:08 GMT+8",
         "pending": false
        },
        {
         "text": " 数字员工 【自动拨测】09:50 对 SYN-CKT-1006 拨测，丢包率约 10%。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 10:05:44 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员L 客户来电确认：10:01 起业务恢复正常，丢包消失。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 10:23:10 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员L 返单。原因：自恢。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 10:49:31 GMT+8",
         "pending": false
        },
        {
         "text": " 邮件系统 收到上游运营商 JP-Carrier 回复邮件，详见邮件详情。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-25 11:30:00 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员M 结单。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障原因",
         "pending": false
        }
       ],
       [
        {
         "text": "分析",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure Analysis",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "【待核实】",
         "pending": true
        }
       ],
       [
        {
         "text": "责任方：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        },
        {
         "text": "；故障位置：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "改进及预防措施",
         "pending": false
        }
       ],
       [
        {
         "text": "Improvement and preventive measures",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "国际公司将持续关注线路运行情况，监控线路运行情况，发现隐患尽早处理，快速响应处置故障。",
         "pending": false
        },
        {
         "text": "【系统默认表述，待审核】",
         "pending": true
        }
       ]
      ]
     }
    ]
   }
  },
  {
   "ticket": {
    "ticket_ref": "SYN-S02",
    "title": "【合成】客户专线业务中断",
    "category": "业务中断",
    "list_status": "已结单",
    "data_class": "synthetic",
    "captured": "2026-09-12T09:00:00+08:00"
   },
   "downloads": {
    "docx": "samples/SYN-S02-company-report.docx",
    "html": "samples/SYN-S02-company-report.html"
   },
   "analysis": {
    "schema_version": "1.0",
    "ticket_ref": "SYN-S02",
    "data_class": "synthetic",
    "data_cutoff": "2026-09-12T09:00:00+08:00",
    "run": {
     "provider": "rules",
     "rules_version": "1.2",
     "prompt_version": null,
     "finished_at": "2026-10-29T04:53:46.071494+00:00"
    },
    "materials": [
     {
      "id": "M01",
      "kind": "ticket_fields",
      "path": "ticket.json",
      "parse_status": "parsed"
     },
     {
      "id": "M02",
      "kind": "process_log",
      "path": "process_log.json",
      "parse_status": "parsed"
     }
    ],
    "evidence": [
     {
      "id": "M01/f:ticket_no",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "ticket_no"
      },
      "text": "SYN-S02"
     },
     {
      "id": "M01/f:customer",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "customer"
      },
      "text": "示例客户乙（合成）"
     },
     {
      "id": "M01/f:circuit_id",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "circuit_id"
      },
      "text": "SYN-CKT-1002"
     },
     {
      "id": "M01/f:created_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "created_at"
      },
      "text": "2026-09-12 01:12:05"
     },
     {
      "id": "M01/f:fault_type",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "fault_type"
      },
      "text": "业务中断"
     },
     {
      "id": "M01/f:occurred_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "occurred_at"
      },
      "text": "2026-09-12 01:05:00"
     },
     {
      "id": "M01/f:recovered_at",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "recovered_at"
      },
      "text": "2026-09-12 02:16:00"
     },
     {
      "id": "M01/f:duration_returned",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "duration_returned"
      },
      "text": "40分钟"
     },
     {
      "id": "M01/f:description",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "description"
      },
      "text": "北京时间 2026-09-12 01:06，自动报障系统检测到客户专线 SYN-CKT-1002 Z 端不通，客户业务中断。"
     },
     {
      "id": "M01/f:cause",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "cause"
      },
      "text": "客户 A 端接入设备按计划进行升级割接，Z 端自动报障系统未同步切换，产生中断报障。"
     },
     {
      "id": "M01/f:handling_dept",
      "material_id": "M01",
      "role": "original",
      "locator": {
       "type": "field",
       "field_key": "handling_dept"
      },
      "text": "城域接入维护组（合成）"
     },
     {
      "id": "M02/log:1",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 1
      },
      "text": "Z 端检测到 SYN-CKT-1002 不通，自动建单。"
     },
     {
      "id": "M02/log:2",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 2
      },
      "text": "已受理。"
     },
     {
      "id": "M02/log:3",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 3
      },
      "text": "查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。"
     },
     {
      "id": "M02/log:4",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 4
      },
      "text": "电话联系客户维护人员，对方称正在进行计划割接，割接窗口 01:00—03:00。"
     },
     {
      "id": "M02/log:5",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 5
      },
      "text": "A 端接入端口 02:15 恢复 UP，业务流量恢复。"
     },
     {
      "id": "M02/log:6",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 6
      },
      "text": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。"
     },
     {
      "id": "M02/log:7",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 7
      },
      "text": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。"
     },
     {
      "id": "M02/log:8",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 8
      },
      "text": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。"
     },
     {
      "id": "M02/log:9",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 9
      },
      "text": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。"
     },
     {
      "id": "M02/log:10",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 10
      },
      "text": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。"
     },
     {
      "id": "M02/log:11",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 11
      },
      "text": "返单。"
     },
     {
      "id": "M02/log:12",
      "material_id": "M02",
      "role": "original",
      "locator": {
       "type": "log_entry",
       "seq": 12
      },
      "text": "结单。"
     }
    ],
    "elements": {
     "start_time": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:occurred_at"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-09-12 01:05:00",
       "iso": "2026-09-12T01:05:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C2",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:created_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 01:12:05",
         "iso": "2026-09-12T01:12:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M01/f:occurred_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 01:05:00",
         "iso": "2026-09-12T01:05:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "fault_start_field"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-09-12 01:06，自动报障系统检测到客户专线 SYN-CKT-1002 Z",
         "iso": "2026-09-12T01:06:00+00:00",
         "tz_source": "explicit",
         "utc_offset": "+00:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "observation"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 01:12:05",
         "iso": "2026-09-12T01:12:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_created"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "01:04 出现 LINK DOWN 告警，Z",
         "iso": "2026-09-12T01:04:00+00:00",
         "tz_source": "explicit",
         "utc_offset": "+00:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "alarm_raised"
       }
      ]
     },
     "end_time": {
      "status": "confirmed",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:6"
      ],
      "issues": [
       "TIME_CANDIDATES_DIFFER"
      ],
      "value": {
       "raw": "2026-09-12 02:16:00",
       "iso": "2026-09-12T02:16:00+08:00",
       "tz_source": "assumed",
       "utc_offset": "+08:00",
       "precision": "second",
       "placeholder": false
      },
      "selected": "C1",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:recovered_at"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:16:00",
         "iso": "2026-09-12T02:16:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "recovery_field"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "noc_check",
        "note": "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。",
        "time": {
         "raw": "02:15",
         "iso": "2026-09-12T02:15:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "minute",
         "placeholder": false
        },
        "time_kind": "alarm_cleared"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:31:05",
         "iso": "2026-09-12T02:31:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:33:40",
         "iso": "2026-09-12T02:33:40+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:36:12",
         "iso": "2026-09-12T02:36:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       },
       {
        "id": "C6",
        "evidence_refs": [
         "M02/log:9"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:40:59",
         "iso": "2026-09-12T02:40:59+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       },
       {
        "id": "C7",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:44:21",
         "iso": "2026-09-12T02:44:21+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       },
       {
        "id": "C8",
        "evidence_refs": [
         "M02/log:11"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 02:52:00",
         "iso": "2026-09-12T02:52:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_returned"
       },
       {
        "id": "C9",
        "evidence_refs": [
         "M02/log:12"
        ],
        "attribution": "system_field",
        "time": {
         "raw": "2026-09-12 08:30:15",
         "iso": "2026-09-12T08:30:15+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "time_kind": "ticket_closed"
       }
      ]
     },
     "phenomenon": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:description",
       "M02/log:1",
       "M02/log:3"
      ],
      "issues": [],
      "value": "客户反馈：北京时间 2026-09-12 01:06，自动报障系统检测到客户专线 SYN-CKT-1002 Z 端不通，客户业务中断。；检查显示：Z 端检测到 SYN-CKT-1002 不通，自动建单。；检查显示：查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:description"
        ],
        "attribution": "customer",
        "description": "北京时间 2026-09-12 01:06，自动报障系统检测到客户专线 SYN-CKT-1002 Z 端不通，客户业务中断。",
        "metric": "告警/状态",
        "scope": "北京时间 2026-09-12 01:06，自动报障系统检测到客户专线 SYN-CKT-1002 Z 端不通，客户业务中断。"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "noc_check",
        "description": "Z 端检测到 SYN-CKT-1002 不通，自动建单。",
        "metric": "告警/状态",
        "scope": "Z 端检测到 SYN-CKT-1002 不通，自动建单。"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "description": "查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。",
        "metric": "告警/状态",
        "scope": "查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。"
       }
      ]
     },
     "responsible_party": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "RESPONSIBILITY_NO_BASIS"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:handling_dept"
        ],
        "attribution": "system_field",
        "party": "城域接入维护组（合成）",
        "basis": "inferred_from_role"
       }
      ]
     },
     "cause": {
      "status": "documented",
      "evidence_refs": [
       "M01/f:cause"
      ],
      "issues": [],
      "value": "客户 A 端接入设备按计划进行升级割接，Z 端自动报障系统未同步切换，产生中断报障。",
      "selected": "C1",
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "statement": "客户 A 端接入设备按计划进行升级割接，Z 端自动报障系统未同步切换，产生中断报障。",
        "cause_kind": "planned_work"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "statement": "电话联系客户维护人员，对方称正在进行计划割接，割接窗口 01:00—03:00。",
        "cause_kind": "planned_work"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "customer",
        "statement": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "cause_kind": "planned_work"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "customer",
        "statement": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "cause_kind": "planned_work"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "customer",
        "statement": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "cause_kind": "planned_work"
       },
       {
        "id": "C6",
        "evidence_refs": [
         "M02/log:9"
        ],
        "attribution": "customer",
        "statement": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "cause_kind": "planned_work"
       },
       {
        "id": "C7",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "customer",
        "statement": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "cause_kind": "planned_work"
       }
      ]
     },
     "handling_process": {
      "status": "documented",
      "evidence_refs": [
       "M02/log:1",
       "M02/log:2",
       "M02/log:3",
       "M02/log:4",
       "M02/log:5",
       "M02/log:6",
       "M02/log:11",
       "M02/log:12"
      ],
      "issues": [],
      "value": [
       {
        "id": "P1",
        "evidence_refs": [
         "M02/log:1"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 01:12:05",
         "iso": "2026-09-12T01:12:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "自动报障系统",
        "action": "Z 端检测到 SYN-CKT-1002 不通，自动建单。",
        "step_kind": "workflow"
       },
       {
        "id": "P2",
        "evidence_refs": [
         "M02/log:2"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 01:14:30",
         "iso": "2026-09-12T01:14:30+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员E",
        "action": "已受理。",
        "step_kind": "workflow"
       },
       {
        "id": "P3",
        "evidence_refs": [
         "M02/log:3"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 01:20:12",
         "iso": "2026-09-12T01:20:12+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员E",
        "action": "查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。",
        "step_kind": "check_result"
       },
       {
        "id": "P4",
        "evidence_refs": [
         "M02/log:4"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 01:31:48",
         "iso": "2026-09-12T01:31:48+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员E",
        "action": "电话联系客户维护人员，对方称正在进行计划割接，割接窗口 01:00—03:00。",
        "step_kind": "communication"
       },
       {
        "id": "P5",
        "evidence_refs": [
         "M02/log:5"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 02:18:26",
         "iso": "2026-09-12T02:18:26+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "工程师F",
        "action": "A 端接入端口 02:15 恢复 UP，业务流量恢复。",
        "step_kind": "communication"
       },
       {
        "id": "P6",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "customer",
        "time": {
         "raw": "2026-09-12 02:31:05",
         "iso": "2026-09-12T02:31:05+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "工程师F",
        "action": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "step_kind": "communication"
       },
       {
        "id": "P11",
        "evidence_refs": [
         "M02/log:11"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 02:52:00",
         "iso": "2026-09-12T02:52:00+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "工程师F",
        "action": "返单。",
        "step_kind": "workflow"
       },
       {
        "id": "P12",
        "evidence_refs": [
         "M02/log:12"
        ],
        "attribution": "noc_check",
        "time": {
         "raw": "2026-09-12 08:30:15",
         "iso": "2026-09-12T08:30:15+08:00",
         "tz_source": "assumed",
         "utc_offset": "+08:00",
         "precision": "second",
         "placeholder": false
        },
        "actor": "值班员G",
        "action": "结单。",
        "step_kind": "workflow"
       }
      ]
     },
     "location": {
      "status": "unknown",
      "evidence_refs": [],
      "issues": [
       "LOCATION_NOT_LOCATED"
      ],
      "candidates": [
       {
        "id": "C1",
        "evidence_refs": [
         "M01/f:cause"
        ],
        "attribution": "system_field",
        "description": "客户 A 端接入设备按计划进行升级割接，Z 端自动报障系统未同步切换，产生中断报障。",
        "role": "customer_site"
       },
       {
        "id": "C2",
        "evidence_refs": [
         "M02/log:6"
        ],
        "attribution": "customer",
        "description": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "role": "customer_site"
       },
       {
        "id": "C3",
        "evidence_refs": [
         "M02/log:7"
        ],
        "attribution": "customer",
        "description": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "role": "customer_site"
       },
       {
        "id": "C4",
        "evidence_refs": [
         "M02/log:8"
        ],
        "attribution": "customer",
        "description": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "role": "customer_site"
       },
       {
        "id": "C5",
        "evidence_refs": [
         "M02/log:9"
        ],
        "attribution": "customer",
        "description": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "role": "customer_site"
       },
       {
        "id": "C6",
        "evidence_refs": [
         "M02/log:10"
        ],
        "attribution": "customer",
        "description": "经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
        "role": "customer_site"
       }
      ]
     }
    },
    "issues": [
     {
      "code": "DURATION_BASIS_MISMATCH",
      "severity": "info",
      "message": "返单历时 40 分钟与系统字段差 71 分钟不同，不能混用口径。",
      "element": null,
      "evidence_refs": [
       "M01/f:duration_returned"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "start_time",
      "evidence_refs": [
       "M01/f:created_at",
       "M01/f:occurred_at",
       "M01/f:description",
       "M02/log:1",
       "M02/log:3"
      ]
     },
     {
      "code": "TIME_CANDIDATES_DIFFER",
      "severity": "warning",
      "message": "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
      "element": "end_time",
      "evidence_refs": [
       "M01/f:recovered_at",
       "M02/log:5",
       "M02/log:6",
       "M02/log:7",
       "M02/log:8",
       "M02/log:9",
       "M02/log:10",
       "M02/log:11",
       "M02/log:12"
      ]
     },
     {
      "code": "RESPONSIBILITY_NO_BASIS",
      "severity": "info",
      "message": "未见明确责任认定，不按供应商或处理部门补齐。",
      "element": "responsible_party",
      "evidence_refs": [
       "M01/f:handling_dept"
      ]
     },
     {
      "code": "LOCATION_NOT_LOCATED",
      "severity": "info",
      "message": "未定位实际故障点，业务端点、告警位置和测试节点只作候选。",
      "element": "location",
      "evidence_refs": [
       "M01/f:cause",
       "M02/log:6",
       "M02/log:7",
       "M02/log:8",
       "M02/log:9",
       "M02/log:10"
      ]
     },
     {
      "code": "DUPLICATE_CONTENT",
      "severity": "info",
      "message": "重复内容已保留来源关系，处理时间线不重复计入。",
      "element": null,
      "evidence_refs": [
       "M02/log:7",
       "M02/log:6"
      ]
     },
     {
      "code": "DUPLICATE_CONTENT",
      "severity": "info",
      "message": "重复内容已保留来源关系，处理时间线不重复计入。",
      "element": null,
      "evidence_refs": [
       "M02/log:8",
       "M02/log:6"
      ]
     },
     {
      "code": "DUPLICATE_CONTENT",
      "severity": "info",
      "message": "重复内容已保留来源关系，处理时间线不重复计入。",
      "element": null,
      "evidence_refs": [
       "M02/log:9",
       "M02/log:6"
      ]
     },
     {
      "code": "DUPLICATE_CONTENT",
      "severity": "info",
      "message": "重复内容已保留来源关系，处理时间线不重复计入。",
      "element": null,
      "evidence_refs": [
       "M02/log:10",
       "M02/log:6"
      ]
     }
    ],
    "suggestions": []
   },
   "company_report": {
    "ticket_ref": "SYN-S02",
    "report_date": "2026年 10 月 29 日",
    "synthetic": true,
    "cells": [
     {
      "row": 0,
      "col": 0,
      "rowspan": 7,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障基本情况",
         "pending": false
        }
       ],
       [
        {
         "text": "The basic situation of failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "客户名称Customer",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 0,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "示例客户乙（合成）",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "电路编号",
         "pending": false
        }
       ],
       [
        {
         "text": "Circuit ID.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 1,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-CKT-1002",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障号: ",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault Ticket no.",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 2,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "SYN-S02",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 1,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "业务类型 Service",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 3,
      "col": 2,
      "rowspan": 1,
      "colspan": 2,
      "label": false,
      "lines": [
       [
        {
         "text": "业务中断",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 1,
      "rowspan": 3,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障时间 Downtime",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "申报时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Time to declare",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 4,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-12 01:05:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "恢复时间",
         "pending": false
        }
       ],
       [
        {
         "text": "Resumed time",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 5,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-12 02:16:00 (GMT+8)",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 2,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障历时",
         "pending": false
        }
       ],
       [
        {
         "text": "Fault duration",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 6,
      "col": 3,
      "rowspan": 1,
      "colspan": 1,
      "label": false,
      "lines": [
       [
        {
         "text": "71分钟",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障现象",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 7,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "客户反馈：北京时间 2026-09-12 01:06，自动报障系统检测到客户专线 SYN-CKT-1002 Z 端不通，客户业务中断。；检查显示：Z 端检测到 SYN-CKT-1002 不通，自动建单。；检查显示：查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "处理过程",
         "pending": false
        }
       ],
       [
        {
         "text": "Process",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 8,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "2026-09-12 01:12:05 GMT+8",
         "pending": false
        },
        {
         "text": " 自动报障系统 Z 端检测到 SYN-CKT-1002 不通，自动建单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 01:14:30 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员E 已受理。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 01:20:12 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员E 查告警：A 端接入端口 01:04 出现 LINK DOWN 告警，Z 端随后上报业务中断。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 01:31:48 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员E 电话联系客户维护人员，对方称正在进行计划割接，割接窗口 01:00—03:00。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 02:18:26 GMT+8",
         "pending": false
        },
        {
         "text": " 工程师F A 端接入端口 02:15 恢复 UP，业务流量恢复。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 02:31:05 GMT+8",
         "pending": false
        },
        {
         "text": " 工程师F 经与客户维护人员电话确认：本次为客户 A 端接入设备计划升级割接（窗口 01:00—03:00），Z 端自动报障未同步切换；客户确认当前线路已正常，同意结单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 02:52:00 GMT+8",
         "pending": false
        },
        {
         "text": " 工程师F 返单。",
         "pending": false
        }
       ],
       [
        {
         "text": "2026-09-12 08:30:15 GMT+8",
         "pending": false
        },
        {
         "text": " 值班员G 结单。",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "故障原因",
         "pending": false
        }
       ],
       [
        {
         "text": "分析",
         "pending": false
        }
       ],
       [
        {
         "text": "Failure Analysis",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 9,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "客户 A 端接入设备按计划进行升级割接，Z 端自动报障系统未同步切换，产生中断报障。",
         "pending": false
        }
       ],
       [
        {
         "text": "责任方：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        },
        {
         "text": "；故障位置：",
         "pending": false
        },
        {
         "text": "【待核实】",
         "pending": true
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 0,
      "rowspan": 1,
      "colspan": 1,
      "label": true,
      "lines": [
       [
        {
         "text": "改进及预防措施",
         "pending": false
        }
       ],
       [
        {
         "text": "Improvement and preventive measures",
         "pending": false
        }
       ]
      ]
     },
     {
      "row": 10,
      "col": 1,
      "rowspan": 1,
      "colspan": 3,
      "label": false,
      "lines": [
       [
        {
         "text": "国际公司将持续关注线路运行情况，监控线路运行情况，发现隐患尽早处理，快速响应处置故障。",
         "pending": false
        },
        {
         "text": "【系统默认表述，待审核】",
         "pending": true
        }
       ]
      ]
     }
    ]
   }
  }
 ]
};
