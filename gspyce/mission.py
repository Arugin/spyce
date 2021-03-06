import time
from math import radians

from spyce.vector import Mat4
import gspyce.simulation
import gspyce.textures
import gspyce.mesh
from gspyce.graphics import *


class MissionGUI(gspyce.simulation.SimulationGUI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rocket_mesh = gspyce.mesh.Square(1)
        self.texture_rocket_on = gspyce.textures.load("rocket_on.png")
        self.texture_rocket_off = gspyce.textures.load("rocket_off.png")

    def draw_rocket(self):
        """Draw the rocket"""

        self.add_pick_object(self.rocket)

        # rocket orientation
        row1, row2, row3 = self.rocket.orientation
        orientation = Mat4([
            [*row1, 0],
            [*row2, 0],
            [*row3, 0],
            [0, 0, 0, 1],
        ])

        original_modelview_matrix = self.modelview_matrix
        transform = self.modelview_matrix @ \
            Mat4.translate(*self.rocket._relative_position) @ \
            Mat4.scale(1e4, 1e4, 1e4) @ \
            orientation
        self.set_modelview_matrix(transform)

        # pick correct texture
        if self.rocket.throttle == 0:
            glBindTexture(GL_TEXTURE_2D, self.texture_rocket_off)
        else:
            glBindTexture(GL_TEXTURE_2D, self.texture_rocket_on)

        # draw texture
        glDisable(GL_CULL_FACE)
        self.set_color(1, 1, 1, 1)
        self.rocket_mesh.draw()
        glEnable(GL_CULL_FACE)

        # all done
        glBindTexture(GL_TEXTURE_2D, 0)
        self.set_modelview_matrix(original_modelview_matrix)

    def draw_body(self, body):
        """Draw a CelestialBody (or a Rocket)"""

        if body == self.rocket:
            return

        super().draw_body(body)

    def draw(self):
        super().draw()

        self.draw_rocket()

    def main(self):
        """Main loop"""
        last = time.time()
        accumulated_time = 0.
        while self.is_running:
            glutMainLoopEvent()

            # passage of time
            now = time.time()
            elapsed = now - last
            last = now
            accumulated_time += elapsed * self.timewarp

            dt = 2.**-5

            # avoid wasting cycles
            if accumulated_time < dt:
                pause = 1./60 - elapsed
                if pause > 0.:
                    time.sleep(pause)
                continue

            # physics simulation
            while accumulated_time > dt:
                if self.rocket.throttle:
                    # physical simulation (integration)
                    delta_t = dt
                else:
                    # logical simulation (just following Kepler orbits)
                    resume_delay = self.rocket.resume_time - self.time
                    next_activity = max(dt, resume_delay)
                    delta_t = (min(accumulated_time, next_activity) // dt) * dt
                accumulated_time -= delta_t
                self.rocket.simulate(self.time, delta_t)
                self.time += delta_t

            self.update()

        glutCloseFunc(None)


def main():
    import spyce.ksp_cfg
    import spyce.rocket

    sim = MissionGUI.from_cli_args()

    def launchpad_to_orbit(rocket):
        # vertical ascent with progressive gravity turn
        sim.log("Phase 1 (vertical take-off)")
        yield lambda: rocket.position[0] > 610e3
        sim.log("Phase 2 (start of gravity turn)")
        rocket.rotate(radians(-45), 1, 0, 0)
        yield lambda: rocket.orbit.apoapsis > 675e3
        sim.log("Phase 3 (end of gravity turn)")
        rocket.rotate(radians(-45), 1, 0, 0)
        yield lambda: rocket.orbit.apoapsis > 700e3
        sim.log("Phase 4 (coasting)")
        rocket.throttle = 0.

        # circularizing
        yield lambda: rocket.position.norm() > 699e3
        sim.log("Phase 5 (circularizing)")
        rocket.rotate(radians(-20), 1, 0, 0)
        rocket.throttle = 1.0
        yield lambda: rocket.orbit.periapsis > 695e3
        sim.log("In orbit")
        rocket.throttle = 0.0

    def program(rocket):
        yield from launchpad_to_orbit(rocket)

        sim.log("Onto the Mun!")
        rocket.throttle = 1.0
        rocket.rotate(radians(58.0515), 1, 0, 0)

        yield lambda: rocket.propellant <= 0.
        sim.log("Out of propellant!")
        rocket.throttle = 0

    body = sim.focus
    rocket = spyce.rocket.Rocket(body, program)
    rocket |= spyce.ksp_cfg.PartSet().make(
        'Size3LargeTank', 'Size3LargeTank', 'Size3EngineCluster',
    )
    rocket.orbit.primary.satellites.append(rocket)

    sim.rocket = rocket
    sim.focus = rocket
    with sim:
        sim.main()


if __name__ == '__main__':
    main()
