import type { Project } from './api/types'

/** Same case as validation/disc_pzt4/project.json. */
export const defaultProject: Project = {
  name: 'PZT-4 disc, a = 10.5 mm, t = 1.5 mm',
  units: 'SI',
  bodies: [
    {
      id: 'disc',
      shape: 'disc',
      params: { radius: 0.0105, thickness: 0.0015, z_offset: 0 },
      material_id: 'PZT-4',
      poling: { direction: '+z' },
    },
  ],
  electrodes: [
    {
      id: 'top',
      body_id: 'disc',
      surface: 'top',
      extent: { kind: 'annulus', r_min: 0, r_max: 0.0105, theta_min: 0, theta_max: 360 },
      terminal_id: 'hot',
    },
    {
      id: 'bottom',
      body_id: 'disc',
      surface: 'bottom',
      extent: { kind: 'annulus', r_min: 0, r_max: 0.0105, theta_min: 0, theta_max: 360 },
      terminal_id: 'gnd',
    },
  ],
  terminals: [
    { id: 'hot', name: 'Input', role: 'port' },
    { id: 'gnd', name: 'Ground', role: 'ground' },
  ],
  study: {
    eigen: { num_modes: 20, freq_shift: 1000, port_condition: 'short' },
    harmonic: { f_start: 20e3, f_stop: 200e3, n_points: 181, spacing: 'lin' },
    ports: [],
    mesh: { max_element_size: 0.25e-3, elements_per_wavelength_at_f_max: 10, order: 2 },
  },
}
