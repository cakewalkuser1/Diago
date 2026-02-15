/**
 * Plain-English translations for technical diagnostic terms.
 * Used for One-Time users who should not see jargon.
 */

export const PLAIN_ENGLISH_CLASS_MAP: Record<string, string> = {
  rolling_element_bearing: "Wear in a spinning part (bearing, pulley, or similar)",
  gear_mesh_drivetrain: "Gears or drivetrain parts making noise",
  belt_drive_friction: "Belt slipping or worn (serpentine, alternator, etc.)",
  hydraulic_flow_cavitation: "Fluid or pump issue (power steering, transmission)",
  electrical_interference: "Electrical parts (alternator, fuel pump, ignition)",
  combustion_impulse: "Engine firing or timing (spark plugs, injectors, etc.)",
  structural_resonance: "Loose or worn mount, shield, or exhaust part",
  lean_condition_bank_1: "Engine may be getting too much air or not enough fuel",
  lean_condition_bank_2: "Engine may be getting too much air or not enough fuel",
  rich_condition: "Engine may be getting too much fuel or not enough air",
  misfire: "Engine cylinder not firing properly",
  knock_detonation: "Engine knock or ping (fuel or timing issue)",
  vacuum_leak: "Air leak in engine vacuum system",
  exhaust_leak: "Leak in exhaust system",
  unknown: "Need more information to narrow it down",
};

export const PLAIN_ENGLISH_FAILURE_MAP: Record<string, string> = {
  lean_condition_bank_1: "Engine may be getting too much air or not enough fuel",
  lean_condition_bank_2: "Engine may be getting too much air or not enough fuel",
  vacuum_leak: "Air is leaking into the engine where it shouldn't",
  maf_sensor_dirty: "Air flow sensor may need cleaning or replacement",
  fuel_pump_weak: "Fuel pump may not be delivering enough fuel",
  injector_clogged: "Fuel injector may be clogged or faulty",
  o2_sensor_faulty: "Oxygen sensor may need replacement",
  exhaust_leak: "Exhaust is leaking before the catalytic converter",
  serpentine_belt: "Drive belt may be worn, loose, or glazed",
  idler_pulley: "Idler pulley bearing may be worn",
  wheel_bearing: "Wheel bearing may be worn",
  alternator_bearing: "Alternator bearing may be worn",
  water_pump_bearing: "Water pump bearing may be worn",
  timing_chain: "Timing chain or guides may be worn",
  motor_mount: "Engine mount may be broken or worn",
  heat_shield: "Heat shield may be loose or rattling",
  spark_plug: "Spark plugs may need replacement",
  ignition_coil: "Ignition coil may be failing",
  knock_sensor: "Knock sensor may need replacement",
  unknown: "Possible cause needs more testing to confirm",
};

/** Convert technical display name to plain English when possible */
export function toPlainEnglish(
  technical: string,
  map: Record<string, string> = PLAIN_ENGLISH_CLASS_MAP
): string {
  if (!technical) return "";
  const key = technical.toLowerCase().replace(/\s+/g, "_");
  const direct = map[key];
  if (direct) return direct;
  const partial = Object.keys(map).find((k) => key.includes(k));
  return partial ? map[partial] : technical;
}
