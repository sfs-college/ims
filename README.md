# Project Blixtro

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-11-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

**Project Blixtro** is a student-driven initiative designed to streamline the management of college-wide assets and inventory across campus departments. The system is powered by **Python Django**, offering a robust and scalable backend for web application development.

For development, the project leverages database systems like SQLite and PostgreSQL, while a production-ready **PostgreSQL** database ensures secure and reliable storage of college inventory data. On the frontend, **HTML**, **SCSS**, and **JavaScript** work together with **Bootstrap** to create a responsive, user-friendly interface that enhances the user experience.

---

## Features 🚀

- **Smart College Inventory Control:** Track, allocate, and manage institutional stock across rooms and departments in real-time.
- **Venue & Room Booking System:** Automated conflict detection and multi-stage approval workflow (Sub-Admin review to Central Admin final sign-off).
- **Student Issue Portal:** A ticketing interface for reporting infrastructure or asset issues with a 3-tier escalation workflow (Incharge -> Sub-Admin -> Central Admin) and TAT (Turnaround Time) tracking.
- **Hybrid Mobile Support:** Packaged using **Capacitor JS** for Android compatibility, enabling on-the-go asset management.

---

## Development Setup 🛠️

To set up and run the Blixtro project locally:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/joisemp/project-blixtro.git
   cd project-blixtro
   ```

2. **Run the local setup script:**
   For Windows environments, use the pre-configured setup batch file:
   ```cmd
   .\script\setup.bat
   ```
   This script will automatically create a virtual environment, install the required packages listed in `requirements.txt`, run migrations, run unit tests, and boot up the Django server.

3. **Manual Setup (Optional):**
   If you prefer to configure the environment manually:
   - Create and activate a Python virtual environment:
     ```bash
     python -m venv venv
     # On Linux/macOS:
     source venv/bin/activate
     # On Windows:
     .\venv\Scripts\activate
     ```
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```
   - Set up environment variables in `src/.env` (refer to `src/.env.example` if available).
   - Run database migrations:
     ```bash
     python src/manage.py migrate
     ```
   - Start the local development server:
     ```bash
     python src/manage.py runserver
     ```

---

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/joisemp"><img src="https://avatars.githubusercontent.com/u/69669027?v=4?s=100" width="100px;" alt="Joise MP"/><br /><sub><b>Joise MP</b></sub></a><br /><a href="https://github.com/joisemp/project-blixtro/commits?author=joisemp" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/kumkum671"><img src="https://avatars.githubusercontent.com/u/146065195?v=4?s=100" width="100px;" alt="kumkum"/><br /><sub><b>Kumkum Sharma</b></sub></a><br /><a href="https://github.com/joisemp/project-blixtro/commits?author=kumkum671" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Nagesh-s36"><img src="https://avatars.githubusercontent.com/u/126268986?v=4?s=100" width="100px;" alt="Nagesh S"/><br /><sub><b>Nagesh S</b></sub></a><br /><a href="#infra-Nagesh-s36" title="Infrastructure (Hosting, Build-Tools, etc)">🚇</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/AqsaMoin"><img src="https://avatars.githubusercontent.com/u/164524187?v=4?s=100" width="100px;" alt="AqsaMoin"/><br /><sub><b>AqsaMoin</b></sub></a><br /><a href="https://github.com/joisemp/project-blixtro/commits?author=AqsaMoin" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/SHIVASHAMBHAVI"><img src="https://avatars.githubusercontent.com/u/164608989?v=4?s=100" width="100px;" alt="SHIVASHAMBHAVI"/><br /><sub><b>SHIVASHAMBHAVI</b></sub></a><br /><a href="#design-SHIVASHAMBHAVI" title="Design">🎨</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/sambrama-M"><img src="https://avatars.githubusercontent.com/u/157901846?v=4?s=100" width="100px;" alt="Sambrama M Salian"/><br /><sub><b>Sambrama M Salian</b></sub></a><br /><a href="#design-sambrama-M" title="Design">🎨</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Pallavihira190"><img src="https://avatars.githubusercontent.com/u/164606297?v=4?s=100" width="100px;" alt="Pallavihira190"/><br /><sub><b>Pallavihira190</b></sub></a><br /><a href="#design-Pallavihira190" title="Design">🎨</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ShahidPashaN"><img src="https://avatars.githubusercontent.com/u/141987808?v=4?s=100" width="100px;" alt="ShahidPashaN"/><br /><sub><b>ShahidPashaN</b></sub></a><br /><a href="#design-ShahidPashaN" title="Design">🎨</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Santhosh-tom"><img src="https://avatars.githubusercontent.com/u/188533038?v=4?s=100" width="100px;" alt="Santhosh-tom"/><br /><sub><b>Santhosh-tom</b></sub></a><br /><a href="#design-Santhosh-tom" title="Design">🎨</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Azhan015"><img src="https://github.com/Azhan015.png" width="100px;" alt="Mohammed Sharif Azhan"/><br /><sub><b>Mohammed Sharif Azhan</b></sub></a><br /><a href="https://github.com/joisemp/project-blixtro/commits?author=Azhan015" title="Code">💻</a> <a href="#infra-Azhan015" title="Infrastructure (Hosting, Build-Tools, etc)">🚇</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Likitha-projects"><img src="https://github.com/Likitha-projects.png" width="100px;" alt="Likitha Rani K"/><br /><sub><b>Likitha Rani K</b></sub></a><br /><a href="https://github.com/joisemp/project-blixtro/commits?author=Likitha-projects" title="Code">💻</a></td>
    </tr>
  </tbody>
</table>
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!
