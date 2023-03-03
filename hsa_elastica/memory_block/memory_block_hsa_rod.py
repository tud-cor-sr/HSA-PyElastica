__doc__ = """Create block-structure class for collection of Cosserat rod systems."""

from elastica.memory_block.memory_block_rod import make_block_memory_metadata
from elastica.rod.data_structures import _RodSymplecticStepperMixin
from elastica.reset_functions_for_block_structure import _reset_scalar_ghost
import numpy as np
from typing import Sequence

from hsa_elastica.rod import HsaRod


class MemoryBlockHsaRod(HsaRod, _RodSymplecticStepperMixin):
    def __init__(self, systems: Sequence):
        self.n_elems_in_rods = np.array([x.n_elems for x in systems], dtype=np.int64)
        self.n_rods = len(systems)
        (
            self.n_elems,
            self.ghost_nodes_idx,
            self.ghost_elems_idx,
            self.ghost_voronoi_idx,
        ) = make_block_memory_metadata(self.n_elems_in_rods)
        self.n_nodes = self.n_elems + 1
        self.n_voronoi = self.n_elems - 1

        # n_nodes_in_rods = self.n_elems_in_rods + 1
        # n_voronois_in_rods = self.n_elems_in_rods - 1

        self.start_idx_in_rod_nodes = np.hstack(
            (0, self.ghost_nodes_idx + 1)
        )  # Start index of subsequent rod
        self.end_idx_in_rod_nodes = np.hstack(
            (self.ghost_nodes_idx, self.n_nodes)
        )  # End index of the rod, Some max size, doesn't really matter
        self.start_idx_in_rod_elems = np.hstack((0, self.ghost_elems_idx[1::2] + 1))
        self.end_idx_in_rod_elems = np.hstack((self.ghost_elems_idx[::2], self.n_elems))
        self.start_idx_in_rod_voronoi = np.hstack((0, self.ghost_voronoi_idx[2::3] + 1))
        self.end_idx_in_rod_voronoi = np.hstack(
            (self.ghost_voronoi_idx[::3], self.n_voronoi)
        )

        # Allocate block structure using system collection.
        self.allocate_block_variables_in_nodes(systems)
        self.allocate_block_variables_in_elements(systems)
        self.allocate_blocks_variables_in_voronoi(systems)
        self.allocate_blocks_variables_for_symplectic_stepper(systems)

        # Reset ghosts of mass, rest length and rest voronoi length to 1. Otherwise
        # since ghosts are not modified, this causes a division by zero error.
        _reset_scalar_ghost(self.mass, self.ghost_nodes_idx, 1.0)
        _reset_scalar_ghost(self.rest_lengths, self.ghost_elems_idx, 1.0)
        _reset_scalar_ghost(self.rest_voronoi_lengths, self.ghost_voronoi_idx, 1.0)
        _reset_scalar_ghost(self.printed_lengths, self.ghost_elems_idx, 1.0)
        _reset_scalar_ghost(self.printed_voronoi_lengths, self.ghost_voronoi_idx, 1.0)

        # Initialize the mixin class for symplectic time-stepper.
        _RodSymplecticStepperMixin.__init__(self)

    def allocate_block_variables_in_nodes(self, systems: Sequence):
        """
        This function takes system collection and allocates the variables on
        node for block-structure and references allocated variables back to the
        systems.

        Parameters
        ----------
        systems

        Returns
        -------

        """

        # Things in nodes that are scalars
        #             0 ("mass", float64[:]),
        map_scalar_dofs_in_rod_nodes = {
            "mass": 0,
            "dissipation_constant_for_forces": 1,
        }
        self.scalar_dofs_in_rod_nodes = np.zeros(
            (len(map_scalar_dofs_in_rod_nodes), self.n_nodes)
        )
        for k, v in map_scalar_dofs_in_rod_nodes.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.scalar_dofs_in_rod_nodes[v], (self.n_nodes,)
            )

        for k, v in map_scalar_dofs_in_rod_nodes.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_nodes[system_idx]
                end_idx = self.end_idx_in_rod_nodes[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Things in nodes that are vectors
        #             0 ("position_collection", float64[:, :]),
        #             1 ("internal_forces", float64[:, :]),
        #             2 ("external_forces", float64[:, :]),
        #             3 ("damping_forces", float64[:, :]),
        # 6 in total
        map_vector_dofs_in_rod_nodes = {
            "position_collection": 0,
            "internal_forces": 1,
            "external_forces": 2,
            "damping_forces": 3,
        }
        self.vector_dofs_in_rod_nodes = np.zeros(
            (len(map_vector_dofs_in_rod_nodes), 3 * self.n_nodes)
        )
        for k, v in map_vector_dofs_in_rod_nodes.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.vector_dofs_in_rod_nodes[v], (3, self.n_nodes)
            )

        for k, v in map_vector_dofs_in_rod_nodes.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_nodes[system_idx]
                end_idx = self.end_idx_in_rod_nodes[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Things in nodes that are matrices
        # Null set

    def allocate_block_variables_in_elements(self, systems: Sequence):
        """
        This function takes system collection and allocates the variables on
        elements for block-structure and references allocated variables back to the
        systems.

        Parameters
        ----------
        systems

        Returns
        -------

        """

        # Things in elements that are scalars
        #             0 ("radius", float64[:]),
        #             1 ("volume", float64[:]),
        #             2 ("density", float64[:]),
        #             3 ("lengths", float64[:]),
        #             4 ("rest_lengths", float64[:]),
        #             5 ("dilatation", float64[:]),
        #             6 ("dilatation_rate", float64[:]),
        #             7 ("dissipation_constant_for_forces", float64[:]),
        #             8 ("dissipation_constant_for_torques", float64[:])
        map_scalar_dofs_in_rod_elems = {
            "radius": 0,
            "volume": 1,
            "density": 2,
            "lengths": 3,
            "rest_lengths": 4,
            "rest_lengths_scale_factor": 5,
            "printed_lengths": 6,
            "dilatation": 7,
            "dilatation_rate": 8,
            "dissipation_constant_for_torques": 9,
            "cross_sectional_area": 10,
            "elastic_modulus": 11,
            "elastic_modulus_scale_factor": 12,
            "shear_modulus": 13,
            "shear_modulus_scale_factor": 14,
            "auxetic": 15,
        }
        self.scalar_dofs_in_rod_elems = np.zeros(
            (len(map_scalar_dofs_in_rod_elems), self.n_elems)
        )
        for k, v in map_scalar_dofs_in_rod_elems.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.scalar_dofs_in_rod_elems[v], (self.n_elems,)
            )

        for k, v in map_scalar_dofs_in_rod_elems.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_elems[system_idx]
                end_idx = self.end_idx_in_rod_elems[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Things in elements that are vectors
        #             0 ("tangents", float64[:, :]),
        #             1 ("sigma", float64[:, :]),
        #             2 ("rest_sigma", float64[:, :]),
        #             3 ("internal_torques", float64[:, :]),
        #             4 ("external_torques", float64[:, :]),
        #             5 ("damping_torques", float64[:, :]),
        #             6 ("internal_stress", float64[:, :]),
        map_vector_dofs_in_rod_elems = {
            "tangents": 0,
            "sigma": 1,
            "rest_sigma": 2,
            "internal_torques": 3,
            "external_torques": 4,
            "damping_torques": 5,
            "internal_stress": 6,
            "second_moment_of_inertia": 7,
        }
        self.vector_dofs_in_rod_elems = np.zeros(
            (len(map_vector_dofs_in_rod_elems), 3 * self.n_elems)
        )
        for k, v in map_vector_dofs_in_rod_elems.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.vector_dofs_in_rod_elems[v], (3, self.n_elems)
            )

        for k, v in map_vector_dofs_in_rod_elems.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_elems[system_idx]
                end_idx = self.end_idx_in_rod_elems[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Things in elements that are matrices
        #             0 ("director_collection", float64[:, :, :]),
        #             1 ("mass_second_moment_of_inertia", float64[:, :, :]),
        #             2 ("inv_mass_second_moment_of_inertia", float64[:, :, :]),
        #             3 ("shear_matrix", float64[:, :, :]),
        map_matrix_dofs_in_rod_elems = {
            "director_collection": 0,
            "mass_second_moment_of_inertia": 1,
            "inv_mass_second_moment_of_inertia": 2,
            "shear_matrix": 3,
        }
        self.matrix_dofs_in_rod_elems = np.zeros(
            (len(map_matrix_dofs_in_rod_elems), 9 * self.n_elems)
        )
        for k, v in map_matrix_dofs_in_rod_elems.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.matrix_dofs_in_rod_elems[v], (3, 3, self.n_elems)
            )

        for k, v in map_matrix_dofs_in_rod_elems.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_elems[system_idx]
                end_idx = self.end_idx_in_rod_elems[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

    def allocate_blocks_variables_in_voronoi(self, systems: Sequence):
        """
        This function takes system collection and allocates the variables on
        voronoi for block-structure and references allocated variables back to the
        systems.

        Parameters
        ----------
        systems

        Returns
        -------

        """

        # Things in voronoi that are scalars
        #             0 ("voronoi_dilatation", float64[:]),
        #             1 ("rest_voronoi_lengths", float64[:]),
        map_scalar_dofs_in_rod_voronois = {
            "voronoi_dilatation": 0,
            "rest_voronoi_lengths": 1,
            "printed_voronoi_lengths": 2,
            "bend_rigidity": 3,
            "bend_rigidity_scale_factor": 4,
            "twist_rigidity": 5,
            "handedness": 6,
        }
        self.scalar_dofs_in_rod_voronois = np.zeros(
            (len(map_scalar_dofs_in_rod_voronois), self.n_voronoi)
        )
        for k, v in map_scalar_dofs_in_rod_voronois.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.scalar_dofs_in_rod_voronois[v], (self.n_voronoi,)
            )

        for k, v in map_scalar_dofs_in_rod_voronois.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_voronoi[system_idx]
                end_idx = self.end_idx_in_rod_voronoi[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Things in voronoi that are vectors
        #             0 ("kappa", float64[:, :]),
        #             1 ("rest_kappa", float64[:, :]),
        #             2 ("internal_couple", float64[:, :]),
        map_vector_dofs_in_rod_voronois = {
            "kappa": 0,
            "rest_kappa": 1,
            "internal_couple": 2,
        }
        self.vector_dofs_in_rod_voronois = np.zeros(
            (len(map_vector_dofs_in_rod_voronois), 3 * self.n_voronoi)
        )
        for k, v in map_vector_dofs_in_rod_voronois.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.vector_dofs_in_rod_voronois[v], (3, self.n_voronoi)
            )

        for k, v in map_vector_dofs_in_rod_voronois.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_voronoi[system_idx]
                end_idx = self.end_idx_in_rod_voronoi[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Things in voronoi that are matrices
        #             0 ("bend_matrix", float64[:, :, :]),
        map_matrix_dofs_in_rod_voronois = {"bend_matrix": 0}
        self.matrix_dofs_in_rod_voronois = np.zeros(
            (len(map_matrix_dofs_in_rod_voronois), 9 * self.n_voronoi)
        )

        for k, v in map_matrix_dofs_in_rod_voronois.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.matrix_dofs_in_rod_voronois[v], (3, 3, self.n_voronoi)
            )

        for k, v in map_matrix_dofs_in_rod_voronois.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_voronoi[system_idx]
                end_idx = self.end_idx_in_rod_voronoi[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

    def allocate_blocks_variables_for_symplectic_stepper(self, systems: Sequence):
        """
        This function takes system collection and allocates the variables used by symplectic
        stepper for block-structure and references allocated variables back to the systems.

        Parameters
        ----------
        systems

        Returns
        -------

        """
        # These vectors are on nodes or on elements, but we stack them together for
        # better memory access. Because we use them together in time-steppers.
        #             0 ("velocity_collection", float64[:, :]),
        #             1 ("omega_collection", float64[:, :]),
        #             2 ("acceleration_collection", float64[:, :]),
        #             3 ("alpha_collection", float64[:, :]),
        # 4 in total

        map_rate_collection = {
            "velocity_collection": 0,
            "omega_collection": 1,
            "acceleration_collection": 2,
            "alpha_collection": 3,
        }
        self.rate_collection = np.zeros((len(map_rate_collection), 3 * self.n_nodes))
        for k, v in map_rate_collection.items():
            self.__dict__[k] = np.lib.stride_tricks.as_strided(
                self.rate_collection[v], (3, self.n_nodes)
            )

        self.__dict__["velocity_collection"] = np.lib.stride_tricks.as_strided(
            self.rate_collection[0], (3, self.n_nodes)
        )

        self.__dict__["omega_collection"] = np.lib.stride_tricks.as_strided(
            self.rate_collection[1],
            (3, self.n_elems),
        )

        self.__dict__["acceleration_collection"] = np.lib.stride_tricks.as_strided(
            self.rate_collection[2],
            (3, self.n_nodes),
        )

        self.__dict__["alpha_collection"] = np.lib.stride_tricks.as_strided(
            self.rate_collection[3],
            (3, self.n_elems),
        )

        # For Dynamic state update of position Verlet create references
        self.v_w_collection = np.lib.stride_tricks.as_strided(
            self.rate_collection[0:2], (2, 3 * self.n_nodes)
        )

        self.dvdt_dwdt_collection = np.lib.stride_tricks.as_strided(
            self.rate_collection[2:-1], (2, 3 * self.n_nodes)
        )

        # Copy systems variables on nodes to block structure
        map_rate_collection_dofs_in_rod_nodes = {
            "velocity_collection": 0,
            "acceleration_collection": 1,
        }
        for k, v in map_rate_collection_dofs_in_rod_nodes.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_nodes[system_idx]
                end_idx = self.end_idx_in_rod_nodes[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )

        # Copy systems variables on nodes to block structure
        map_rate_collection_dofs_in_rod_elems = {
            "omega_collection": 0,
            "alpha_collection": 1,
        }
        for k, v in map_rate_collection_dofs_in_rod_elems.items():
            for system_idx, system in enumerate(systems):
                start_idx = self.start_idx_in_rod_elems[system_idx]
                end_idx = self.end_idx_in_rod_elems[system_idx]
                self.__dict__[k][..., start_idx:end_idx] = system.__dict__[k].copy()
                system.__dict__[k] = np.ndarray.view(
                    self.__dict__[k][..., start_idx:end_idx]
                )
