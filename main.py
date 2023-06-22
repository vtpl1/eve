from sqlalchemy import create_engine, select

from tables import Address, Base, User, VLoginUser

engine = create_engine("mysql+mysqlconnector://root:root@172.16.4.24:3309/ivms_30", echo=True, pool_recycle=3600)
# Base.metadata.create_all(engine)

from sqlalchemy.orm import Session

# with Session(engine) as session:
#     spongebob = User(
#         name="spongebob",
#         fullname="Spongebob Squarepants",
#         addresses=[Address(email_address="spongebob@sqlalchemy.org")],
#     )
#     sandy = User(
#         name="sandy",
#         fullname="Sandy Cheeks",
#         addresses=[
#             Address(email_address="sandy@sqlalchemy.org"),
#             Address(email_address="sandy@squirrelpower.org"),
#         ],
#     )
#     patrick = User(name="patrick", fullname="Patrick Star")
#     session.add_all([spongebob, sandy, patrick])
#     session.commit()
    
with Session(engine) as session:
    stmt = select(VLoginUser.id, VLoginUser.password).where(VLoginUser.id.in_(["admin"]))
    for user in session.execute(stmt):
        print(user)