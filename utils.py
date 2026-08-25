"""Utility helpers for the Dynamx addon

This module contains a few small helpers used across the addon. Keep
these functions tiny and dependency-free so they are safe to call from
operators.
"""

import bpy
from mathutils import Vector


def workspace_exists(name: str) -> bool:
    return any(ws.name == name for ws in bpy.data.workspaces)


def ensure_collection(name: str, parent=None, scene: bpy.types.Scene = None) -> bpy.types.Collection:
    """Return an existing collection by name or create and link it.

    Args:
        name: collection name to ensure
        parent: either a bpy.types.Collection to link under as a child,
                or None to link into the provided scene.collection (or
                the current scene if none provided).
        scene: optional scene used to link top-level collections when
               parent is not a collection.

    Returns:
        bpy.types.Collection object (existing or newly created)
    """
    col = bpy.data.collections.get(name)
    if col:
        return col

    col = bpy.data.collections.new(name)
    try:
        if isinstance(parent, bpy.types.Collection):
            try:
                parent.children.link(col)
                return col
            except Exception:
                pass

        if isinstance(parent, str):
            parent_col = bpy.data.collections.get(parent)
            if parent_col:
                try:
                    parent_col.children.link(col)
                    return col
                except Exception:
                    pass

        s = scene if scene is not None else bpy.context.scene
        try:
            s.collection.children.link(col)
        except Exception:
            try:
                bpy.context.scene.collection.children.link(col)
            except Exception:
                pass
    except Exception:
        pass
    return col


def world_aabb(obj: bpy.types.Object):
    """Compute world-space AABB center and size (half-extents) for an object.

    Returns (center: Vector, size: Vector) where size is full extents (not half).
    """
    try:
        bb_local = [Vector(c) for c in obj.bound_box]
        world_pts = [obj.matrix_world @ p for p in bb_local]
        xs = [p.x for p in world_pts]
        ys = [p.y for p in world_pts]
        zs = [p.z for p in world_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)
        center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
        size = Vector((max_x - min_x, max_y - min_y, max_z - min_z))
        return center, size
    except Exception:
        try:
            center = obj.matrix_world.to_translation()
            size = obj.dimensions if getattr(obj, 'dimensions', None) is not None else Vector((0.0, 0.0, 0.0))
            return center, size
        except Exception:
            return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
