import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Body, MaterialSummary } from '../api/types'
import { bodyRect } from '../geometry'
import { useStore } from '../store'
import { MM } from '../units'
import { NumberField, Section, SelectField } from './fields'

export function GeometryEditor() {
  const bodies = useStore((s) => s.project.bodies)
  const updateBody = useStore((s) => s.updateBody)
  const addBody = useStore((s) => s.addBody)
  const removeBody = useStore((s) => s.removeBody)
  const [materials, setMaterials] = useState<MaterialSummary[]>([])

  useEffect(() => {
    api.materials().then(setMaterials, () => setMaterials([]))
  }, [])

  return (
    <Section
      title="Geometry & material"
      actions={
        <button className="small" onClick={addBody} title="Stack another layer on top">
          + Layer
        </button>
      }
    >
      {bodies.map((b) => (
        <BodyCard
          key={b.id}
          body={b}
          materials={materials}
          onChange={(nb) => updateBody(b.id, nb)}
          onRemove={bodies.length > 1 ? () => removeBody(b.id) : undefined}
        />
      ))}
    </Section>
  )
}

function BodyCard({
  body,
  materials,
  onChange,
  onRemove,
}: {
  body: Body
  materials: MaterialSummary[]
  onChange: (b: Body) => void
  onRemove?: () => void
}) {
  const setShape = (shape: Body['shape']) => {
    if (shape === body.shape) return
    const r = bodyRect(body)
    const common = { id: body.id, material_id: body.material_id, poling: body.poling }
    const z = { thickness: r.z1 - r.z0, z_offset: r.z0 }
    onChange(
      shape === 'disc'
        ? { ...common, shape, params: { radius: r.r1, ...z } }
        : { ...common, shape, params: { inner_radius: r.r1 / 2, outer_radius: r.r1, ...z } },
    )
  }
  const materialOptions = materials.length
    ? materials.map((m) => ({ value: m.id, label: m.name }))
    : [{ value: body.material_id, label: body.material_id }]
  const source = materials.find((m) => m.id === body.material_id)?.source

  return (
    <div className="card">
      <div className="card-title">
        <code>{body.id}</code>
        {onRemove && (
          <button className="link danger" onClick={onRemove} title="Remove this body and its electrodes">
            remove
          </button>
        )}
      </div>
      <div className="grid2">
        <SelectField label="Shape" value={body.shape} options={['disc', 'ring'] as const} onChange={setShape} />
        <SelectField
          label="Poling"
          value={typeof body.poling?.direction === 'string' ? body.poling.direction : '+z'}
          options={['+z', '-z'] as const}
          onChange={(direction) => onChange({ ...body, poling: { direction } })}
        />
        {body.shape === 'disc' ? (
          <NumberField
            label="Radius"
            unit="mm"
            scale={MM}
            min={0}
            value={body.params.radius}
            onChange={(radius) => onChange({ ...body, params: { ...body.params, radius } })}
          />
        ) : (
          <>
            <NumberField
              label="Inner radius"
              unit="mm"
              scale={MM}
              min={0}
              value={body.params.inner_radius}
              onChange={(inner_radius) => onChange({ ...body, params: { ...body.params, inner_radius } })}
            />
            <NumberField
              label="Outer radius"
              unit="mm"
              scale={MM}
              min={0}
              value={body.params.outer_radius}
              onChange={(outer_radius) => onChange({ ...body, params: { ...body.params, outer_radius } })}
            />
          </>
        )}
        <NumberField
          label="Thickness"
          unit="mm"
          scale={MM}
          min={0}
          value={body.params.thickness}
          onChange={(thickness) => onChange({ ...body, params: { ...body.params, thickness } } as Body)}
        />
        <NumberField
          label="Bottom z"
          unit="mm"
          scale={MM}
          value={body.params.z_offset ?? 0}
          onChange={(z_offset) => onChange({ ...body, params: { ...body.params, z_offset } } as Body)}
        />
      </div>
      <SelectField
        label="Material"
        value={body.material_id}
        options={materialOptions}
        onChange={(material_id) => onChange({ ...body, material_id })}
      />
      {source && <p className="hint">{source}</p>}
    </div>
  )
}
